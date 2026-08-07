from __future__ import annotations

import hashlib
import json
import os
import sys
import types
from argparse import Namespace
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
import pyarrow as pa
import pytest

from src.experiments.build_closure_pipe_sequences import (
    DEFAULT_RUNTIME_CONFIG,
    INPUT_COLUMNS,
    MODEL_STATE_MAPPINGS,
    SEQUENCE_COLUMNS,
    SEQUENCE_VERSION,
    SURFACE_ID,
    TARGET_COLUMNS,
    TARGET_TO_NEXT_INPUT_MAPPING,
    _file_record,
    expected_cpu_execution_policy_record,
    sequence_arrow_table,
    write_sequence_parquet,
)
from src.experiments.closure_contract import load_yaml_mapping
from src.experiments.train_closure_pipe import (
    EarlyStoppingState,
    FitAvailability,
    E0_MC_AUTHORITY_PATH,
    E0_MC_LOCK_PATH,
    E0_MC_MANIFEST_PATH,
    E0_MD_GATE_PATH,
    E0_ME_GATE_PATH,
    E0_MF_GATE_PATH,
    E0_MG_GATE_PATH,
    E0_MG_LOCK_PATH,
    E0_MG_MANIFEST_PATH,
    E0_MG_SCHEMA_PATH,
    E0_MH_GATE_PATH,
    E0_MH_LOCK_PATH,
    E0_MH_MANIFEST_PATH,
    E0_MI_GATE_PATH,
    E0_MI_LOCK_PATH,
    E0_MI_MANIFEST_PATH,
    E0_MI_SCHEMA_PATH,
    E0_MJ_LOCK_PATH,
    E0_MJ_MANIFEST_PATH,
    E0_MK_LOCK_PATH,
    E0_MK_MANIFEST_PATH,
    E0_MK_SCHEMA_PATH,
    E0_ML_LOCK_PATH,
    E0_ML_MANIFEST_PATH,
    E0_MM_LOCK_PATH,
    E0_MM_MANIFEST_PATH,
    E0_MM_SCHEMA_PATH,
    E0_MN_LOCK_PATH,
    E0_MN_MANIFEST_PATH,
    E0_MO_LOCK_PATH,
    E0_MO_MANIFEST_PATH,
    E0_MO_SCHEMA_PATH,
    MODEL_ARTIFACT_OUTPUT_NAMES,
    P1_FIT_FAILURE_REASON_COUNTS,
    P1_FIT_STATUS_COUNTS,
    P1_SEQUENCE_AUDITOR_PATH,
    P1_SEQUENCE_20260612_AUDITOR_PATH,
    P1_SEQUENCE_20260613_AUDITOR_PATH,
    P1_SEQUENCE_20260614_AUDITOR_PATH,
    P1_SEQUENCE_314159_AUDITOR_PATH,
    P1_SEQUENCE_POINTER_PATH,
    P1_SEQUENCE_20260612_POINTER_PATH,
    P1_SEQUENCE_20260613_POINTER_PATH,
    P1_SEQUENCE_20260614_POINTER_PATH,
    P1_SEQUENCE_314159_POINTER_PATH,
    P1_20260612_AUTHORITY_SOURCE_PATHS,
    P1_20260614_AUTHORITY_SOURCE_PATHS,
    P1_314159_AUTHORITY_SOURCE_PATHS,
    SequenceInputContract,
    TemporalModelInputContract,
    WindowBundle,
    P0_ARTIFACT_BUILDER_RECORD,
    _TemporalOutputTransaction,
    _open_real_output_parent,
    _path_entry_exists,
    _run_temporal_slot,
    _temporal_slot_guard,
    _write_model_unavailable_evidence,
    _checkpoint_objective,
    advance_early_stopping,
    canonical_epoch_batches,
    closure_training_loss,
    collect_sequence_input_contract,
    configure_deterministic_runtime,
    fit_available_slot,
    inspect_fit_availability,
    load_window_bundle,
    assert_temporal_slot_outputs_absent,
    validate_sequence_common_origin_identity,
    validate_sequence_completion_manifest,
    validate_sequence_physical_schema,
    validate_temporal_runtime_contract,
    assert_sequence_input_contract_unchanged,
    builder_records_from_temporal_validation_authority,
    builder_records_from_p1_seed_20260612_temporal_consumer_authority,
    builder_records_from_p1_seed_20260613_temporal_consumer_authority,
    builder_records_from_p1_seed_20260614_temporal_consumer_authority,
    builder_records_from_p1_seed_314159_temporal_consumer_authority,
    validate_p1_temporal_consumer_seed_20260612_authority,
    validate_p1_temporal_consumer_seed_20260613_authority,
    validate_p1_temporal_consumer_seed_20260614_authority,
    validate_p1_temporal_consumer_seed_314159_authority,
    validate_p1_temporal_consumer_schema_subset_authority,
    validate_sequence_manifest_builder_binding,
)
from src.experiments.train_pipe_grud import make_model


def _sequence_row(
    site_id: str,
    origin: str,
    target: str,
    role: str,
    *,
    status: str = "success",
    reason: str = "",
) -> dict[str, object]:
    origin_period: Any = pd.Period(origin, freq="M")
    row: dict[str, object] = {
        "sequence_version": SEQUENCE_VERSION,
        "surface_id": "closure_v1_wqp_adaptive_no_current_chla",
        "model_id": "P0",
        "base_seed": None,
        "source_id": "wqp",
        "site_id": site_id,
        "common_origin_id": f"origin-{site_id}-{origin}",
        "evaluation_unit_id": f"unit-{site_id}-{origin}",
        "holdout_group_id": f"wqp::{site_id}",
        "assignment_role": "development",
        "time_role": role,
        "origin_year_month": origin,
        "target_year_month": target,
        "history_start_year_month": str(origin_period - 11),
        "history_end_year_month": origin,
        "history_length_months": 12,
        "sequence_status": status,
        "failure_reason": reason,
    }
    for index, column in enumerate(INPUT_COLUMNS):
        row[column] = np.full(12, 0.1 + index / 100.0, dtype=np.float32)
    for index, column in enumerate(TARGET_COLUMNS):
        row[column] = np.float32(0.2 + index / 100.0)
    if status != "success":
        for column in INPUT_COLUMNS:
            row[column] = None
        for column in TARGET_COLUMNS:
            row[column] = np.float32(np.nan)
    return row


def _sequence_frame(*, calibration_failure: bool = False) -> pd.DataFrame:
    rows = [
        _sequence_row("z-site", "2018-08", "2018-09", "training"),
        _sequence_row("a-site", "2018-07", "2018-08", "training"),
        _sequence_row("a-site", "2020-08", "2020-09", "model_selection"),
        _sequence_row(
            "a-site",
            "2021-08",
            "2021-09",
            "calibration_threshold",
            status="autoregressive_target_unavailable" if calibration_failure else "success",
            reason="missing_target_state" if calibration_failure else "",
        ),
    ]
    return pd.DataFrame(rows, columns=SEQUENCE_COLUMNS)


def _common_from_sequences(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for sequence in frame.to_dict(orient="records"):
        origin: Any = pd.Period(str(sequence["origin_year_month"]), freq="M")
        for horizon in (1, 2, 3):
            rows.append(
                {
                    "surface_id": sequence["surface_id"],
                    "source_id": sequence["source_id"],
                    "site_id": sequence["site_id"],
                    "common_origin_id": sequence["common_origin_id"],
                    "evaluation_unit_id": (
                        sequence["evaluation_unit_id"]
                        if horizon == 1
                        else f"{sequence['evaluation_unit_id']}-h{horizon}"
                    ),
                    "holdout_group_id": sequence["holdout_group_id"],
                    "assignment_role": sequence["assignment_role"],
                    "time_role": sequence["time_role"],
                    "origin_year_month": sequence["origin_year_month"],
                    "target_year_month": str(origin + horizon),
                    "horizon_months": horizon,
                    "history_start_year_month": sequence["history_start_year_month"],
                    "history_end_year_month": sequence["history_end_year_month"],
                    "history_length_months": sequence["history_length_months"],
                }
            )
    return pd.DataFrame(rows)


def _p1_consumer_schema_subset_authority(
    *,
    builder_record: Mapping[str, Any],
    lock_record: Mapping[str, Any],
    companion_record: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "gate": "E0-MG",
        "publication_verified": True,
        "remote_publication_verified": True,
        "historical_e0_mf_verified": True,
        "historical_mf_effective_loader_called": False,
        "p_e0_mf_absent": True,
        "schema_subset_compatibility_corrected": True,
        "schema_subset_preflight_verified": True,
        "schema_supported_subset_verified": True,
        "minimum_keyword_absent": True,
        "format_keyword_absent": True,
        "numeric_bounds_validated_semantically": True,
        "timestamp_validated_semantically": True,
        "historical_e0_me_verified": True,
        "historical_me_effective_loader_called": False,
        "p_e0_me_absent": True,
        "pytest_summary_parser_corrected": True,
        "historical_e0_md_verified": True,
        "p_e0_md_absent": True,
        "authorization_effective": True,
        "p1_consumer_authorized": True,
        "p1_fit_authorized": True,
        "p1_sequence_bundle_verified": True,
        "in_process_audit_verified": True,
        "consumer_namespace_absent": True,
        "historical_e0_dltvm_verified": True,
        "historical_dltvm_effective_loader_called": False,
        "authorized_model_id": "P1",
        "authorized_base_seed": 1729,
        "authorized_device": "cpu",
        "sequence_fit_available": False,
        "expected_slot_status": "model_unavailable",
        "expected_fit_status": "not_attempted",
        "expected_failure_reason": "sequence_fit_rows_unavailable",
        "auditor_execution_mode": "in_process_callable",
        "python_auditor_subprocess_used": False,
        "batch_seed_execution_authorized": False,
        "retry_authorized": False,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
        "schema_subset_preflight_evidence": {
            "gate": "E0-MG",
            "schema_path": E0_MG_SCHEMA_PATH.as_posix(),
            "schema_bytes": 1,
            "schema_sha256": "3" * 64,
            "supported_subset_verified": True,
            "minimum_keyword_absent": True,
            "format_keyword_absent": True,
        },
        "p1_artifact_builder_record": dict(builder_record),
        "current_runtime_builder_record": dict(builder_record),
        "e0_mc_context_authorization": {"gate": "E0-MC"},
        "authority_input_records": [
            {
                **dict(lock_record),
                "role": "external_p1_temporal_consumer_schema_subset_patch_lock",
            },
            {
                **dict(companion_record),
                "role": "p1_temporal_consumer_schema_subset_patch_companion",
            },
        ],
        "in_process_audit_evidence": {
            "execution_mode": "in_process_callable",
            "callable_module": "src.experiments.audit_closure_p1_sequence_bundle",
            "callable_name": "audit_p1_sequence_bundle",
            "callable_qualname": "audit_p1_sequence_bundle",
            "callable_source_path": P1_SEQUENCE_AUDITOR_PATH.as_posix(),
            "callable_code_filename": P1_SEQUENCE_AUDITOR_PATH.as_posix(),
            "callable_git_commit": "82c0bc10a8b17ab700a8f0c28491a60572a11d81",
            "callable_source_git": {
                "path": P1_SEQUENCE_AUDITOR_PATH.as_posix(),
                "role": "p1_sequence_bundle_auditor_callable",
                "bytes": 1,
                "sha256": "1" * 64,
            },
            "callable_source_physical": {
                "path": P1_SEQUENCE_AUDITOR_PATH.as_posix(),
                "role": "p1_sequence_bundle_auditor_callable",
                "bytes": 1,
                "sha256": "1" * 64,
            },
            "audit_version": "closure_p1_seed_1729_sequence_bundle_audit_v1",
            "status": "validated",
            "model_id": "P1",
            "base_seed": 1729,
            "intent_origins": 9_732,
            "successful_origins": 9_227,
            "failed_origins": 505,
            "fit_successful_origins": 8_925,
            "fit_unavailable_origins": 488,
            "calibration_unavailable_origins": 17,
            "fit_failure_reason_counts": dict(P1_FIT_FAILURE_REASON_COUNTS),
            "sequence_fit_available": False,
            "expected_slot_status": "model_unavailable",
            "expected_fit_status": "not_attempted",
            "expected_failure_reason": "sequence_fit_rows_unavailable",
            "result_bytes": 1,
            "result_sha256": "2" * 64,
            "auditor_read_only": True,
            "consumer_executed": False,
            "fit_executed": False,
            "dvc_operation_executed": False,
            "future_outcomes_accessed": False,
        },
        "e0_md_context_authorization": {
            "gate": "E0-MD",
            "historical_e0_dltvm_verified": True,
            "historical_dltvm_effective_loader_called": False,
        },
        "e0_me_context_authorization": {
            "gate": "E0-ME",
            "patch_head": "1b30cd658acc9e46779e907e3efb30511f646983",
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
        },
        "e0_mf_context_authorization": {
            "gate": "E0-MF",
            "patch_head": "ba5d42f391af1c9574a6c27a711083dd56b30147",
            "p_e0_mf_absent": True,
            "historical_git_authority_verified": True,
            "historical_e0_me_verified": True,
            "historical_e0_md_verified": True,
            "historical_e0_dltvm_verified": True,
            "historical_mf_effective_loader_called": False,
            "effective_loader_called": False,
            "pytest_summary_parser_corrected": True,
            "schema_definition_failure_recorded": True,
            "p_e0_me_absent": True,
            "p_e0_md_absent": True,
            "p1_consumer_authorized": False,
            "p1_fit_authorized": False,
            "evaluation_authorized": False,
            "e0_u_authorized": False,
            "future_outcomes_accessed": False,
        },
        "fit_availability": {
            "sequence_fit_available": False,
            "fit_status_counts": dict(P1_FIT_STATUS_COUNTS),
            "fit_failure_reason_counts": dict(P1_FIT_FAILURE_REASON_COUNTS),
            "calibration_failure_count": 17,
            "expected_slot_status": "model_unavailable",
            "expected_fit_status": "not_attempted",
            "expected_failure_reason": "sequence_fit_rows_unavailable",
            "replacement_used": False,
        },
    }


def _p1_20260612_consumer_authority(
    *,
    builder_record: Mapping[str, Any],
    mh_lock_record: Mapping[str, Any],
    mh_companion_record: Mapping[str, Any],
    mi_lock_record: Mapping[str, Any],
    mi_companion_record: Mapping[str, Any],
    auditor_record: Mapping[str, Any],
) -> dict[str, Any]:
    auditor_with_role = {
        **dict(auditor_record),
        "role": "p1_sequence_bundle_auditor_callable",
    }


    return {
        "gate": "E0-MI",
        "publication_verified": True,
        "remote_publication_verified": True,
        "historical_e0_mg_verified": True,
        "historical_mg_effective_loader_called": False,
        "historical_e0_mh_verified": True,
        "historical_mh_effective_loader_called": False,
        "p1_1729_slot_preserved": True,
        "p1_20260612_sequence_bundle_verified": True,
        "schema_subset_preflight_verified": True,
        "schema_supported_subset_verified": True,
        "minimum_keyword_absent": True,
        "format_keyword_absent": True,
        "numeric_bounds_validated_semantically": True,
        "timestamp_validated_semantically": True,
        "in_process_audit_verified": True,
        "consumer_namespace_absent": True,
        "later_seed_namespaces_absent": True,
        "progression_prelock_verified": True,
        "authorization_effective": True,
        "p1_consumer_authorized": True,
        "p1_fit_authorized": False,
        "fit_attempt_authorized": False,
        "p1_sequence_builder_authorized": False,
        "dvc_commands_authorized": False,
        "authorized_model_id": "P1",
        "authorized_base_seed": 20_260_612,
        "authorized_device": "cpu",
        "sequence_fit_available": False,
        "expected_slot_status": "model_unavailable",
        "expected_fit_status": "not_attempted",
        "expected_failure_reason": "sequence_fit_rows_unavailable",
        "auditor_execution_mode": "in_process_callable",
        "python_auditor_subprocess_used": False,
        "batch_seed_execution_authorized": False,
        "retry_authorized": False,
        "replacement_authorized": False,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
        "schema_subset_preflight_evidence": {
            "gate": "E0-MI",
            "schema_path": E0_MI_SCHEMA_PATH.as_posix(),
            "schema_bytes": 1,
            "schema_sha256": "3" * 64,
            "supported_subset_verified": True,
            "minimum_keyword_absent": True,
            "format_keyword_absent": True,
        },
        "p1_artifact_builder_record": dict(builder_record),
        "current_runtime_builder_record": dict(builder_record),
        "state_consumer_authority": None,
        "sequence_authority_input_records": [
            {
                **dict(mh_lock_record),
                "role": "external_p1_sequence_seed_20260612_patch_lock",
            },
            {
                **dict(mh_companion_record),
                "role": "p1_sequence_seed_20260612_patch_companion",
            },
        ],
        "authority_input_records": [
            {
                **dict(mi_lock_record),
                "role": "external_p1_temporal_consumer_seed_20260612_patch_lock",
            },
            {
                **dict(mi_companion_record),
                "role": "p1_temporal_consumer_seed_20260612_patch_companion",
            },
        ],
        "in_process_audit_evidence": {
            "execution_mode": "in_process_callable",
            "callable_module": (
                "src.experiments.audit_closure_p1_seed_20260612_sequence_bundle"
            ),
            "callable_name": "audit_p1_seed_20260612_sequence_bundle",
            "callable_qualname": "audit_p1_seed_20260612_sequence_bundle",
            "callable_source_path": P1_SEQUENCE_20260612_AUDITOR_PATH.as_posix(),
            "callable_code_filename": P1_SEQUENCE_20260612_AUDITOR_PATH.as_posix(),
            "callable_git_commit": "b448e1fb0ee75b6135da11f0ea9a8877d89e0ee1",
            "callable_source_git": auditor_with_role,
            "callable_source_physical": auditor_with_role,
            "audit_version": "closure_p1_seed_20260612_sequence_bundle_audit_v1",
            "status": "validated",
            "model_id": "P1",
            "base_seed": 20_260_612,
            "intent_origins": 9_732,
            "successful_origins": 9_227,
            "failed_origins": 505,
            "fit_successful_origins": 8_925,
            "fit_unavailable_origins": 488,
            "calibration_unavailable_origins": 17,
            "fit_failure_reason_counts": dict(P1_FIT_FAILURE_REASON_COUNTS),
            "sequence_fit_available": False,
            "expected_slot_status": "model_unavailable",
            "expected_fit_status": "not_attempted",
            "expected_failure_reason": "sequence_fit_rows_unavailable",
            "result_bytes": 1,
            "result_sha256": "2" * 64,
            "auditor_read_only": True,
            "consumer_executed": False,
            "fit_executed": False,
            "dvc_operation_executed": False,
            "future_outcomes_accessed": False,
        },
        "fit_availability": {
            "sequence_fit_available": False,
            "fit_status_counts": dict(P1_FIT_STATUS_COUNTS),
            "fit_failure_reason_counts": dict(P1_FIT_FAILURE_REASON_COUNTS),
            "calibration_failure_count": 17,
            "expected_slot_status": "model_unavailable",
            "expected_fit_status": "not_attempted",
            "expected_failure_reason": "sequence_fit_rows_unavailable",
            "replacement_used": False,
        },
    }


def _p1_20260613_consumer_authority(
    *,
    builder_record: Mapping[str, Any],
    mj_lock_record: Mapping[str, Any],
    mj_companion_record: Mapping[str, Any],
    mk_lock_record: Mapping[str, Any],
    mk_companion_record: Mapping[str, Any],
    auditor_record: Mapping[str, Any],
) -> dict[str, Any]:
    authority = _p1_20260612_consumer_authority(
        builder_record=builder_record,
        mh_lock_record=mj_lock_record,
        mh_companion_record=mj_companion_record,
        mi_lock_record=mk_lock_record,
        mi_companion_record=mk_companion_record,
        auditor_record=auditor_record,
    )
    for field in (
        "historical_e0_mg_verified",
        "historical_mg_effective_loader_called",
        "historical_e0_mh_verified",
        "historical_mh_effective_loader_called",
        "p1_20260612_sequence_bundle_verified",
    ):
        authority.pop(field)
    authority.update(
        {
            "gate": "E0-MK",
            "historical_e0_mi_verified": True,
            "historical_mi_effective_loader_called": False,
            "historical_e0_mj_verified": True,
            "historical_mj_effective_loader_called": False,
            "p1_20260612_slot_preserved": True,
            "p1_20260613_sequence_bundle_verified": True,
            "authorized_base_seed": 20_260_613,
            "schema_subset_preflight_evidence": {
                "gate": "E0-MK",
                "schema_path": E0_MK_SCHEMA_PATH.as_posix(),
                "schema_bytes": 1,
                "schema_sha256": "3" * 64,
                "supported_subset_verified": True,
                "minimum_keyword_absent": True,
                "format_keyword_absent": True,
            },
            "sequence_authority_input_records": [
                {
                    **dict(mj_lock_record),
                    "role": "external_p1_sequence_seed_20260613_patch_lock",
                },
                {
                    **dict(mj_companion_record),
                    "role": "p1_sequence_seed_20260613_patch_companion",
                },
            ],
            "authority_input_records": [
                {
                    **dict(mk_lock_record),
                    "role": (
                        "external_p1_temporal_consumer_seed_20260613_patch_lock"
                    ),
                },
                {
                    **dict(mk_companion_record),
                    "role": "p1_temporal_consumer_seed_20260613_patch_companion",
                },
            ],
        }
    )
    audit = dict(authority["in_process_audit_evidence"])
    auditor_with_role = {
        **dict(auditor_record),
        "role": "p1_sequence_bundle_auditor_callable",
    }
    audit.update(
        {
            "callable_module": (
                "src.experiments.audit_closure_p1_seed_20260613_sequence_bundle"
            ),
            "callable_name": "audit_p1_seed_20260613_sequence_bundle",
            "callable_qualname": "audit_p1_seed_20260613_sequence_bundle",
            "callable_source_path": P1_SEQUENCE_20260613_AUDITOR_PATH.as_posix(),
            "callable_code_filename": P1_SEQUENCE_20260613_AUDITOR_PATH.as_posix(),
            "callable_git_commit": "a25863c05730d65d0fb3454a608243b2c9eca639",
            "callable_source_git": auditor_with_role,
            "callable_source_physical": auditor_with_role,
            "audit_version": "closure_p1_seed_20260613_sequence_bundle_audit_v1",
            "base_seed": 20_260_613,
        }
    )
    authority["in_process_audit_evidence"] = audit
    return authority


def _p1_20260614_consumer_authority(
    *,
    builder_record: Mapping[str, Any],
    ml_lock_record: Mapping[str, Any],
    ml_companion_record: Mapping[str, Any],
    mm_lock_record: Mapping[str, Any],
    mm_companion_record: Mapping[str, Any],
    auditor_record: Mapping[str, Any],
) -> dict[str, Any]:
    authority = _p1_20260613_consumer_authority(
        builder_record=builder_record,
        mj_lock_record=ml_lock_record,
        mj_companion_record=ml_companion_record,
        mk_lock_record=mm_lock_record,
        mk_companion_record=mm_companion_record,
        auditor_record=auditor_record,
    )
    for field in (
        "historical_e0_mi_verified",
        "historical_mi_effective_loader_called",
        "historical_e0_mj_verified",
        "historical_mj_effective_loader_called",
        "p1_20260613_sequence_bundle_verified",
    ):
        authority.pop(field)
    authority.update(
        {
            "gate": "E0-MM",
            "historical_e0_mk_verified": True,
            "historical_mk_effective_loader_called": False,
            "historical_e0_ml_verified": True,
            "historical_ml_effective_loader_called": False,
            "p1_20260613_slot_preserved": True,
            "p1_20260614_sequence_bundle_verified": True,
            "authorized_base_seed": 20_260_614,
            "schema_subset_preflight_evidence": {
                "gate": "E0-MM",
                "schema_path": E0_MM_SCHEMA_PATH.as_posix(),
                "schema_bytes": 1,
                "schema_sha256": "3" * 64,
                "supported_subset_verified": True,
                "minimum_keyword_absent": True,
                "format_keyword_absent": True,
            },
            "sequence_authority_input_records": [
                {
                    **dict(ml_lock_record),
                    "role": "external_p1_sequence_seed_20260614_patch_lock",
                },
                {
                    **dict(ml_companion_record),
                    "role": "p1_sequence_seed_20260614_patch_companion",
                },
            ],
            "authority_input_records": [
                {
                    **dict(mm_lock_record),
                    "role": (
                        "external_p1_temporal_consumer_seed_20260614_patch_lock"
                    ),
                },
                {
                    **dict(mm_companion_record),
                    "role": "p1_temporal_consumer_seed_20260614_patch_companion",
                },
            ],
        }
    )
    audit = dict(authority["in_process_audit_evidence"])
    auditor_with_role = {
        **dict(auditor_record),
        "role": "p1_sequence_bundle_auditor_callable",
    }
    audit.update(
        {
            "callable_module": (
                "src.experiments.audit_closure_p1_seed_20260614_sequence_bundle"
            ),
            "callable_name": "audit_p1_seed_20260614_sequence_bundle",
            "callable_qualname": "audit_p1_seed_20260614_sequence_bundle",
            "callable_source_path": P1_SEQUENCE_20260614_AUDITOR_PATH.as_posix(),
            "callable_code_filename": P1_SEQUENCE_20260614_AUDITOR_PATH.as_posix(),
            "callable_git_commit": "9b40b2bea49084aab1ba37a1a5e4b87261a83fae",
            "callable_source_git": auditor_with_role,
            "callable_source_physical": auditor_with_role,
            "audit_version": "closure_p1_seed_20260614_sequence_bundle_audit_v1",
            "base_seed": 20_260_614,
        }
    )
    authority["in_process_audit_evidence"] = audit
    return authority


def _p1_314159_consumer_authority(
    *,
    builder_record: Mapping[str, Any],
    mn_lock_record: Mapping[str, Any],
    mn_companion_record: Mapping[str, Any],
    mo_lock_record: Mapping[str, Any],
    mo_companion_record: Mapping[str, Any],
    auditor_record: Mapping[str, Any],
) -> dict[str, Any]:
    authority = _p1_20260614_consumer_authority(
        builder_record=builder_record,
        ml_lock_record=mn_lock_record,
        ml_companion_record=mn_companion_record,
        mm_lock_record=mo_lock_record,
        mm_companion_record=mo_companion_record,
        auditor_record=auditor_record,
    )
    for field in (
        "historical_e0_mk_verified",
        "historical_mk_effective_loader_called",
        "historical_e0_ml_verified",
        "historical_ml_effective_loader_called",
        "p1_20260614_sequence_bundle_verified",
    ):
        authority.pop(field)
    authority.update(
        {
            "gate": "E0-MO",
            "historical_e0_mm_verified": True,
            "historical_mm_effective_loader_called": False,
            "historical_e0_mn_verified": True,
            "historical_mn_effective_loader_called": False,
            "p1_20260613_slot_preserved": True,
            "p1_20260614_slot_preserved": True,
            "p1_314159_sequence_bundle_verified": True,
            "authorized_base_seed": 314_159,
            "schema_subset_preflight_evidence": {
                "gate": "E0-MO",
                "schema_path": E0_MO_SCHEMA_PATH.as_posix(),
                "schema_bytes": 1,
                "schema_sha256": "3" * 64,
                "supported_subset_verified": True,
                "minimum_keyword_absent": True,
                "format_keyword_absent": True,
            },
            "sequence_authority_input_records": [
                {
                    **dict(mn_lock_record),
                    "role": "external_p1_sequence_seed_314159_patch_lock",
                },
                {
                    **dict(mn_companion_record),
                    "role": "p1_sequence_seed_314159_patch_companion",
                },
            ],
            "authority_input_records": [
                {
                    **dict(mo_lock_record),
                    "role": (
                        "external_p1_temporal_consumer_seed_314159_patch_lock"
                    ),
                },
                {
                    **dict(mo_companion_record),
                    "role": "p1_temporal_consumer_seed_314159_patch_companion",
                },
            ],
        }
    )
    audit = dict(authority["in_process_audit_evidence"])
    auditor_with_role = {
        **dict(auditor_record),
        "role": "p1_sequence_bundle_auditor_callable",
    }
    audit.update(
        {
            "callable_module": (
                "src.experiments.audit_closure_p1_seed_314159_sequence_bundle"
            ),
            "callable_name": "audit_p1_seed_314159_sequence_bundle",
            "callable_qualname": "audit_p1_seed_314159_sequence_bundle",
            "callable_source_path": P1_SEQUENCE_314159_AUDITOR_PATH.as_posix(),
            "callable_code_filename": P1_SEQUENCE_314159_AUDITOR_PATH.as_posix(),
            "callable_git_commit": "2d69cc82f2611aaebef245bbffd38b4fed0c82a9",
            "callable_source_git": auditor_with_role,
            "callable_source_physical": auditor_with_role,
            "audit_version": "closure_p1_seed_314159_sequence_bundle_audit_v1",
            "base_seed": 314_159,
        }
    )
    authority["in_process_audit_evidence"] = audit
    return authority




def test_window_loader_uses_canonical_utf8_order_and_does_not_fit_calibration() -> None:
    bundle = load_window_bundle(
        _sequence_frame(calibration_failure=True),
        model_id="P0",
        base_seed=1729,
        enforce_locked_denominators=False,
    )

    assert bundle.metadata[["site_id", "origin_year_month"]].values.tolist() == [
        ["a-site", "2018-07"],
        ["a-site", "2020-08"],
        ["a-site", "2021-08"],
        ["z-site", "2018-08"],
    ]
    assert bundle.x.shape == (4, 12, 13)
    assert bundle.y.shape == (4, 9)
    assert np.isnan(bundle.subset("calibration_threshold").x).all()
    assert np.isfinite(bundle.subset("training").x).all()


def test_window_loader_rejects_retained_failure_in_fit_roles() -> None:
    frame = _sequence_frame()
    training = frame["time_role"].eq("training")
    frame.loc[training, "sequence_status"] = "input_history_unavailable"
    frame.loc[training, "failure_reason"] = "missing_history_state"
    for index in frame.index[training]:
        for column in INPUT_COLUMNS:
            frame.at[index, column] = None
        for column in TARGET_COLUMNS:
            frame.at[index, column] = np.nan

    with pytest.raises(ValueError, match="retained failures"):
        load_window_bundle(
            frame,
            model_id="P0",
            base_seed=1729,
            enforce_locked_denominators=False,
        )


def test_batch_digest_uses_compact_json_lines_over_torch_randperm() -> None:
    pytest.importorskip("torch")
    keys = [
        ["wqp", "a", "2018-01", "2018-02"],
        ["wqp", "b", "2018-01", "2018-02"],
        ["wqp", "c", "2018-01", "2018-02"],
    ]
    batches, observed = canonical_epoch_batches(keys, base_seed=1729, epoch=1, batch_size=2)
    records = []
    for batch_number, indices in enumerate(batches, start=1):
        records.append([1, batch_number, [keys[int(index)] for index in indices]])
    expected_payload = b"".join(
        json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
        for record in records
    )

    assert observed == hashlib.sha256(expected_payload).hexdigest()
    assert observed == "166a2bae27e3ea0d9f0c66a992241d7e63936e85bb5b1e1c715c796f8a2c1444"
    assert canonical_epoch_batches(keys, base_seed=1729, epoch=1, batch_size=2)[1] == observed
    assert canonical_epoch_batches(keys, base_seed=1729, epoch=2, batch_size=2)[1] != observed


def test_locked_loss_is_weighted_nll_plus_unit_weight_mse() -> None:
    torch = pytest.importorskip("torch")
    mu = torch.zeros((2, 9), dtype=torch.float32)
    logvar = torch.zeros((2, 9), dtype=torch.float32)
    target = torch.ones((2, 9), dtype=torch.float32)
    weights = torch.ones(9, dtype=torch.float32)

    assert float(closure_training_loss(mu, logvar, target, weights)) == pytest.approx(1.5)


def test_early_stopping_is_patience_five_with_earliest_tie() -> None:
    state = EarlyStoppingState()
    state = advance_early_stopping(state, epoch=1, objective=1.0)
    for epoch in range(2, 6):
        state = advance_early_stopping(state, epoch=epoch, objective=1.0)
        assert state.should_stop is False
    state = advance_early_stopping(state, epoch=6, objective=1.0)

    assert state.should_stop is True
    assert state.best_epoch == 1
    assert state.epochs_without_improvement == 5


def test_checkpoint_objective_is_mean_of_nine_per_target_relative_ratios() -> None:
    targets = [column.removeprefix("target_") for column in TARGET_COLUMNS]
    metrics = pd.DataFrame(
        {
            "target": ["all", *targets],
            "rmse": [999.0, 1.0, *([10.0] * 8)],
            "mae": [999.0, 1.0, *([10.0] * 8)],
        }
    )
    persistence_rmse = np.asarray([0.5, *([20.0] * 8)], dtype=np.float64)
    persistence_mae = np.asarray([0.5, *([20.0] * 8)], dtype=np.float64)

    observed = _checkpoint_objective(metrics, (persistence_rmse, persistence_mae))
    assert observed == pytest.approx((2.0 + 8 * 0.5) / 9.0)
    assert observed != pytest.approx(81.0 / 160.5)


def test_p0_p1_common_seed_produces_identical_initialization() -> None:
    torch = pytest.importorskip("torch")
    configure_deterministic_runtime(1729, "cpu")
    first = make_model(13, 9, 96, 1, 0.0, "add_last")
    first_state = {key: value.detach().clone() for key, value in first.state_dict().items()}
    configure_deterministic_runtime(1729, "cpu")
    second = make_model(13, 9, 96, 1, 0.0, "add_last")

    assert all(torch.equal(first_state[key], value) for key, value in second.state_dict().items())
    with pytest.raises(ValueError, match="must be 'cpu'"):
        configure_deterministic_runtime(1729, "auto")


def test_cpu_runtime_still_seeds_cuda_substream_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    torch = pytest.importorskip("torch")
    calls: list[int] = []
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "manual_seed_all", lambda seed: calls.append(int(seed)))

    configure_deterministic_runtime(1729, "cpu")
    assert 1729 in calls


def test_failed_fit_rows_are_reported_as_unavailable_without_tensorization() -> None:
    frame = _sequence_frame()
    training = frame["time_role"].eq("training")
    frame.loc[training, "sequence_status"] = "model_slot_unavailable"
    frame.loc[training, "failure_reason"] = "anfis_model_slot_unavailable"
    for index in frame.index[training]:
        for column in INPUT_COLUMNS:
            frame.at[index, column] = None
        for column in TARGET_COLUMNS:
            frame.at[index, column] = np.nan

    availability = inspect_fit_availability(
        frame,
        model_id="P0",
        base_seed=1729,
        enforce_locked_denominators=False,
    )
    assert availability.available is False
    assert availability.failure_reason == "sequence_fit_rows_unavailable"
    assert availability.fit_status_counts["model_slot_unavailable"] == 2


def test_failed_fit_rows_accept_only_fully_null_fixed_size_tensors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as sequence_module

    monkeypatch.setattr(sequence_module, "PROJECT_ROOT", tmp_path)
    frame = _sequence_frame()
    training = frame["time_role"].eq("training")
    frame.loc[training, "sequence_status"] = "model_slot_unavailable"
    frame.loc[training, "failure_reason"] = "anfis_model_slot_unavailable"
    for index in frame.index[training]:
        for column in INPUT_COLUMNS:
            frame.at[index, column] = None
        for column in TARGET_COLUMNS:
            frame.at[index, column] = np.nan

    output = tmp_path / "sequence_with_failed_fit_rows.parquet"
    write_sequence_parquet(frame, output)
    restored = pd.read_parquet(output, columns=list(SEQUENCE_COLUMNS))

    availability = inspect_fit_availability(
        restored,
        model_id="P0",
        base_seed=1729,
        enforce_locked_denominators=False,
    )
    assert availability.available is False

    failure_index = restored.index[training][0]
    invalid_tensors = (
        np.array([np.nan] * 11 + [0.0], dtype=np.float32),
        np.full(11, np.nan, dtype=np.float32),
        np.full(13, np.nan, dtype=np.float32),
        np.zeros(12, dtype=np.float32),
        np.full(12, np.inf, dtype=np.float32),
    )
    for invalid in invalid_tensors:
        restored.at[failure_index, INPUT_COLUMNS[0]] = invalid
        with pytest.raises(ValueError, match="nullable tensors only"):
            inspect_fit_availability(
                restored,
                model_id="P0",
                base_seed=1729,
                enforce_locked_denominators=False,
            )


def test_temporal_constants_match_authoritative_runtime() -> None:
    validate_temporal_runtime_contract(load_yaml_mapping(DEFAULT_RUNTIME_CONFIG))


def test_locked_trainer_rejects_a_truncated_sequence_table() -> None:
    with pytest.raises(ValueError, match="denominator drifted"):
        inspect_fit_availability(_sequence_frame(), model_id="P0", base_seed=1729)


def test_window_reader_rejects_nonintegral_seed_and_history_values() -> None:
    p1 = _sequence_frame()
    p1["model_id"] = "P1"
    p1["base_seed"] = 1729.9
    with pytest.raises(ValueError, match="seed differs"):
        inspect_fit_availability(
            p1,
            model_id="P1",
            base_seed=1729,
            enforce_locked_denominators=False,
        )

    bad_history = _sequence_frame()
    bad_history["history_length_months"] = 12.9
    with pytest.raises(ValueError, match="history length"):
        inspect_fit_availability(
            bad_history,
            model_id="P0",
            base_seed=1729,
            enforce_locked_denominators=False,
        )


def test_sequence_schema_and_completion_manifest_are_physically_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _sequence_frame()
    validate_sequence_physical_schema(sequence_arrow_table(frame).schema)
    bad_schema = pa.schema(
        [
            pa.field(
                field.name,
                pa.list_(pa.float64(), 12) if field.name == "x_yN" else field.type,
                nullable=field.nullable,
            )
            for field in sequence_arrow_table(frame).schema
        ]
    )
    with pytest.raises(ValueError, match="physical input field"):
        validate_sequence_physical_schema(bad_schema)
    for column, replacement, message in (
        ("base_seed", pa.float64(), "base_seed"),
        ("history_length_months", pa.float64(), "history_length_months"),
        ("site_id", pa.int64(), "identity field"),
    ):
        drifted = pa.schema(
            [
                pa.field(
                    field.name,
                    replacement if field.name == column else field.type,
                    nullable=field.nullable,
                )
                for field in sequence_arrow_table(frame).schema
            ]
        )
        with pytest.raises(ValueError, match=message):
            validate_sequence_physical_schema(drifted)

    from src.experiments import build_closure_pipe_sequences as sequence_module
    from src.experiments import train_closure_pipe as training_module

    monkeypatch.setattr(sequence_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(training_module, "PROJECT_ROOT", tmp_path)
    builder_path = tmp_path / "src/experiments/build_closure_pipe_sequences.py"
    builder_path.parent.mkdir(parents=True)
    builder_path.write_bytes(b"builder")
    sequence_path = tmp_path / "sequence.parquet"
    summary_path = tmp_path / "sequence_summary.csv"
    common_path = tmp_path / "common.parquet"
    common_completion_path = tmp_path / "common_manifest.json"
    sequence_path.write_bytes(b"sequence")
    summary_path.write_bytes(b"summary")
    common_path.write_bytes(b"common")
    common_completion_path.write_bytes(b"completion")
    record = _file_record(sequence_path)
    summary_record = _file_record(summary_path)
    required_inputs = [_file_record(common_path), _file_record(common_completion_path)]
    script_record = _file_record(builder_path)
    expected_inputs = [script_record, *required_inputs]
    payload = {
        "manifest_version": "closure_pipe_sequence_manifest_v1",
        "status": "completed",
        "generated_at_utc": "2026-08-03T12:00:00+00:00",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": "P0",
        "base_seed": None,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "completion_marker_written_last": True,
        "cpu_execution_policy": expected_cpu_execution_policy_record(),
        "script": script_record,
        "source_code": [script_record],
        "input_state_mapping": MODEL_STATE_MAPPINGS["P0"],
        "target_state_mapping": MODEL_STATE_MAPPINGS["P0"],
        "target_to_next_input_mapping": TARGET_TO_NEXT_INPUT_MAPPING,
        "input_columns": list(INPUT_COLUMNS),
        "target_columns": list(TARGET_COLUMNS),
        "optional_context_columns": [],
        "serialization": {
            "rows_per_common_origin": 1,
            "input_physical_type": "fixed_size_list<float32>[12]",
            "target_physical_type": "float32",
            "canonical_order": [
                "source_id",
                "site_id",
                "origin_year_month",
                "target_year_month",
            ],
        },
        "counts": {
            "intent_origins": 9732,
            "role_counts": {
                "training": 8352,
                "model_selection": 1061,
                "calibration_threshold": 319,
            },
        },
        "inputs": expected_inputs,
        "outputs": [record, summary_record],
    }
    validate_sequence_completion_manifest(
        payload,
        sequence_record=record,
        summary_record=summary_record,
        expected_input_records=expected_inputs,
        artifact_builder_record=script_record,
        model_id="P0",
        base_seed=1729,
    )
    extra_payload = {**payload, "unexpected": True}
    with pytest.raises(ValueError, match="top-level dialect"):
        validate_sequence_completion_manifest(
            extra_payload,
            sequence_record=record,
            summary_record=summary_record,
            expected_input_records=expected_inputs,
            artifact_builder_record=script_record,
            model_id="P0",
            base_seed=1729,
        )
    payload["outputs"] = [{**record, "sha256": "0" * 64}, summary_record]
    with pytest.raises(ValueError, match="hash/bytes"):
        validate_sequence_completion_manifest(
            payload,
            sequence_record=record,
            summary_record=summary_record,
            expected_input_records=expected_inputs,
            artifact_builder_record=script_record,
            model_id="P0",
            base_seed=1729,
        )


def test_sequence_manifest_rejects_builder_or_common_input_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as sequence_module
    from src.experiments import train_closure_pipe as training_module

    monkeypatch.setattr(sequence_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(training_module, "PROJECT_ROOT", tmp_path)
    builder_path = tmp_path / "src/experiments/build_closure_pipe_sequences.py"
    builder_path.parent.mkdir(parents=True)
    builder_path.write_bytes(b"builder")
    sequence_path = tmp_path / "sequence.parquet"
    summary_path = tmp_path / "summary.csv"
    common_path = tmp_path / "common.parquet"
    for path in (sequence_path, summary_path, common_path):
        path.write_bytes(path.name.encode("utf-8"))
    sequence_record = _file_record(sequence_path)
    summary_record = _file_record(summary_path)
    common_record = _file_record(common_path)
    script_record = _file_record(builder_path)
    payload: dict[str, object] = {
        "manifest_version": "closure_pipe_sequence_manifest_v1",
        "status": "completed",
        "generated_at_utc": "2026-08-03T12:00:00+00:00",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": "P0",
        "base_seed": None,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "completion_marker_written_last": True,
        "cpu_execution_policy": expected_cpu_execution_policy_record(),
        "script": {**script_record, "sha256": "0" * 64},
        "source_code": [script_record],
        "input_state_mapping": MODEL_STATE_MAPPINGS["P0"],
        "target_state_mapping": MODEL_STATE_MAPPINGS["P0"],
        "target_to_next_input_mapping": TARGET_TO_NEXT_INPUT_MAPPING,
        "input_columns": list(INPUT_COLUMNS),
        "target_columns": list(TARGET_COLUMNS),
        "optional_context_columns": [],
        "serialization": {
            "rows_per_common_origin": 1,
            "input_physical_type": "fixed_size_list<float32>[12]",
            "target_physical_type": "float32",
            "canonical_order": [
                "source_id",
                "site_id",
                "origin_year_month",
                "target_year_month",
            ],
        },
        "counts": {
            "intent_origins": 9732,
            "role_counts": {
                "training": 8352,
                "model_selection": 1061,
                "calibration_threshold": 319,
            },
        },
        "inputs": [script_record, {**common_record, "sha256": "f" * 64}],
        "outputs": [sequence_record, summary_record],
    }
    with pytest.raises(ValueError, match="exact builder code"):
        validate_sequence_completion_manifest(
            payload,
            sequence_record=sequence_record,
            summary_record=summary_record,
            expected_input_records=[script_record, common_record],
            artifact_builder_record=script_record,
            model_id="P0",
            base_seed=1729,
        )
    payload["script"] = script_record
    with pytest.raises(ValueError, match="differs from physical bytes"):
        validate_sequence_completion_manifest(
            payload,
            sequence_record=sequence_record,
            summary_record=summary_record,
            expected_input_records=[script_record, common_record],
            artifact_builder_record=script_record,
            model_id="P0",
            base_seed=1729,
        )
    extra_path = tmp_path / "extra.json"
    extra_path.write_bytes(b"extra")
    payload["inputs"] = [script_record, common_record, _file_record(extra_path)]
    with pytest.raises(ValueError, match="input path set drifted"):
        validate_sequence_completion_manifest(
            payload,
            sequence_record=sequence_record,
            summary_record=summary_record,
            expected_input_records=[script_record, common_record],
            artifact_builder_record=script_record,
            model_id="P0",
            base_seed=1729,
        )
    payload["inputs"] = [
        {**script_record, "path": builder_path.as_posix()},
        common_record,
    ]
    with pytest.raises(ValueError, match="repository-relative"):
        validate_sequence_completion_manifest(
            payload,
            sequence_record=sequence_record,
            summary_record=summary_record,
            expected_input_records=[script_record, common_record],
            artifact_builder_record=script_record,
            model_id="P0",
            base_seed=1729,
        )


def test_published_p0_manifest_binds_historical_builder_separately_from_live_runtime() -> None:
    from src.experiments import train_closure_pipe as module

    manifest_path = (
        Path(__file__).resolve().parents[1]
        / "reports/closure_v1/01_surface/sequences/P0/expert_no_current_manifest.json"
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert validate_sequence_manifest_builder_binding(
        payload,
        artifact_builder_record=P0_ARTIFACT_BUILDER_RECORD,
    ) == P0_ARTIFACT_BUILDER_RECORD

    live_builder = _file_record(module.PROJECT_ROOT / module.SEQUENCE_BUILDER_PATH)
    assert live_builder != P0_ARTIFACT_BUILDER_RECORD
    artifact, runtime = builder_records_from_temporal_validation_authority(
        {
            "p0_artifact_builder_record": P0_ARTIFACT_BUILDER_RECORD,
            "current_runtime_builder_record": live_builder,
        }
    )
    assert artifact == P0_ARTIFACT_BUILDER_RECORD
    assert runtime == live_builder

    with pytest.raises(ValueError, match="exact builder code"):
        validate_sequence_manifest_builder_binding(
            payload,
            artifact_builder_record=live_builder,
        )
    with pytest.raises(ValueError, match="artifact builder authority drifted"):
        builder_records_from_temporal_validation_authority(
            {
                "p0_artifact_builder_record": {
                    **P0_ARTIFACT_BUILDER_RECORD,
                    "sha256": "0" * 64,
                },
                "current_runtime_builder_record": live_builder,
            }
        )


def test_p1_consumer_schema_subset_authority_separates_builder_and_mg_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as sequence_module
    from src.experiments import train_closure_pipe as module

    monkeypatch.setattr(sequence_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    builder = tmp_path / module.SEQUENCE_BUILDER_PATH
    lock = tmp_path / E0_MG_LOCK_PATH
    companion = tmp_path / E0_MG_MANIFEST_PATH
    for path, content in (
        (builder, b"e0-mc-builder"),
        (lock, b"mg-lock"),
        (companion, b"mg-companion"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    builder_record = _file_record(builder)
    authority = _p1_consumer_schema_subset_authority(
        builder_record=builder_record,
        lock_record=_file_record(lock),
        companion_record=_file_record(companion),
    )

    artifact, current, context, authority_inputs = (
        validate_p1_temporal_consumer_schema_subset_authority(
            authority,
            model_id="P1",
            base_seed=1729,
            device="cpu",
        )
    )

    assert artifact == current == builder_record
    assert context == {"gate": "E0-MC"}
    assert authority_inputs == (_file_record(lock), _file_record(companion))
    drifted = {
        **authority,
        "fit_availability": {
            **authority["fit_availability"],
            "sequence_fit_available": True,
        },
    }
    with pytest.raises(ValueError, match="fit-availability contract drifted"):
        validate_p1_temporal_consumer_schema_subset_authority(
            drifted,
            model_id="P1",
            base_seed=1729,
            device="cpu",
        )
    audit_drifted = {
        **authority,
        "in_process_audit_evidence": {
            **authority["in_process_audit_evidence"],
            "fit_unavailable_origins": 487,
        },
    }
    with pytest.raises(ValueError, match="in-process audit evidence drifted"):
        validate_p1_temporal_consumer_schema_subset_authority(
            audit_drifted,
            model_id="P1",
            base_seed=1729,
            device="cpu",
        )
    schema_uncorrected = {**authority, "schema_subset_compatibility_corrected": False}
    with pytest.raises(ValueError, match="E0-MG authorization predicates drifted"):
        validate_p1_temporal_consumer_schema_subset_authority(
            schema_uncorrected,
            model_id="P1",
            base_seed=1729,
            device="cpu",
        )
    semantic_bounds_unverified = {
        **authority,
        "numeric_bounds_validated_semantically": False,
    }
    with pytest.raises(ValueError, match="E0-MG authorization predicates drifted"):
        validate_p1_temporal_consumer_schema_subset_authority(
            semantic_bounds_unverified,
            model_id="P1",
            base_seed=1729,
            device="cpu",
        )
    schema_preflight_drifted = {
        **authority,
        "schema_subset_preflight_evidence": {
            **authority["schema_subset_preflight_evidence"],
            "schema_sha256": "not-a-sha256",
        },
    }
    with pytest.raises(ValueError, match="schema-subset preflight evidence drifted"):
        validate_p1_temporal_consumer_schema_subset_authority(
            schema_preflight_drifted,
            model_id="P1",
            base_seed=1729,
            device="cpu",
        )
    parser_uncorrected = {**authority, "pytest_summary_parser_corrected": False}
    with pytest.raises(ValueError, match="E0-MG authorization predicates drifted"):
        validate_p1_temporal_consumer_schema_subset_authority(
            parser_uncorrected,
            model_id="P1",
            base_seed=1729,
            device="cpu",
        )
    p_e0_mf_present = {**authority, "p_e0_mf_absent": False}
    with pytest.raises(ValueError, match="E0-MG authorization predicates drifted"):
        validate_p1_temporal_consumer_schema_subset_authority(
            p_e0_mf_present,
            model_id="P1",
            base_seed=1729,
            device="cpu",
        )
    missing_mf = {**authority, "e0_mf_context_authorization": None}
    with pytest.raises(ValueError, match="E0-MF context authorization"):
        validate_p1_temporal_consumer_schema_subset_authority(
            missing_mf,
            model_id="P1",
            base_seed=1729,
            device="cpu",
        )
    missing_me = {**authority, "e0_me_context_authorization": None}
    with pytest.raises(ValueError, match="E0-ME context authorization"):
        validate_p1_temporal_consumer_schema_subset_authority(
            missing_me,
            model_id="P1",
            base_seed=1729,
            device="cpu",
        )
    missing_md = {**authority, "e0_md_context_authorization": None}
    with pytest.raises(ValueError, match="E0-MD context authorization"):
        validate_p1_temporal_consumer_schema_subset_authority(
            missing_md,
            model_id="P1",
            base_seed=1729,
            device="cpu",
        )
    missing_dltvm_context = {
        **authority,
        "e0_md_context_authorization": {"gate": "E0-MD"},
    }
    with pytest.raises(ValueError, match="E0-MD context authorization"):
        validate_p1_temporal_consumer_schema_subset_authority(
            missing_dltvm_context,
            model_id="P1",
            base_seed=1729,
            device="cpu",
        )
    wrong_authority_role = {
        **authority,
        "authority_input_records": [
            {
                **authority["authority_input_records"][0],
                "role": "external_p1_temporal_consumer_pytest_summary_patch_lock",
            },
            dict(authority["authority_input_records"][1]),
        ],
    }
    with pytest.raises(ValueError, match="E0-MG authority input path/role drifted"):
        validate_p1_temporal_consumer_schema_subset_authority(
            wrong_authority_role,
            model_id="P1",
            base_seed=1729,
            device="cpu",
        )


def test_p1_20260612_authority_binds_mh_mi_builder_and_auditor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as sequence_module
    from src.experiments import train_closure_pipe as module

    monkeypatch.setattr(sequence_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    physical_paths = (
        module.SEQUENCE_BUILDER_PATH,
        E0_MH_LOCK_PATH,
        E0_MH_MANIFEST_PATH,
        E0_MI_LOCK_PATH,
        E0_MI_MANIFEST_PATH,
        P1_SEQUENCE_20260612_AUDITOR_PATH,
    )
    for relative in physical_paths:
        physical = tmp_path / relative
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_bytes(relative.as_posix().encode("utf-8"))
    builder_record = _file_record(tmp_path / module.SEQUENCE_BUILDER_PATH)
    authority = _p1_20260612_consumer_authority(
        builder_record=builder_record,
        mh_lock_record=_file_record(tmp_path / E0_MH_LOCK_PATH),
        mh_companion_record=_file_record(tmp_path / E0_MH_MANIFEST_PATH),
        mi_lock_record=_file_record(tmp_path / E0_MI_LOCK_PATH),
        mi_companion_record=_file_record(tmp_path / E0_MI_MANIFEST_PATH),
        auditor_record=_file_record(tmp_path / P1_SEQUENCE_20260612_AUDITOR_PATH),
    )
    artifact, current, state_context, sequence_inputs, consumer_inputs = (
        validate_p1_temporal_consumer_seed_20260612_authority(
            authority,
            model_id="P1",
            base_seed=20_260_612,
            device="cpu",
        )
    )
    assert artifact == current == builder_record
    assert state_context is None
    assert sequence_inputs == (
        _file_record(tmp_path / E0_MH_LOCK_PATH),
        _file_record(tmp_path / E0_MH_MANIFEST_PATH),
    )
    assert consumer_inputs == (
        _file_record(tmp_path / E0_MI_LOCK_PATH),
        _file_record(tmp_path / E0_MI_MANIFEST_PATH),
    )
    assert builder_records_from_p1_seed_20260612_temporal_consumer_authority(
        authority
    ) == (builder_record, builder_record)

    for model_id, base_seed, device in (
        ("P0", 20_260_612, "cpu"),
        ("P1", 1_729, "cpu"),
        ("P1", 20_260_613, "cpu"),
        ("P1", 20_260_612, "cuda"),
    ):
        with pytest.raises(ValueError, match="only P1 seed 20260612"):
            validate_p1_temporal_consumer_seed_20260612_authority(
                authority,
                model_id=model_id,
                base_seed=base_seed,
                device=device,
            )
    fit_drifted = {
        **authority,
        "fit_availability": {
            **authority["fit_availability"],
            "fit_status_counts": {
                "success": 8_924,
                "autoregressive_target_unavailable": 489,
            },
        },
    }
    with pytest.raises(ValueError, match="fit-availability contract drifted"):
        validate_p1_temporal_consumer_seed_20260612_authority(
            fit_drifted,
            model_id="P1",
            base_seed=20_260_612,
            device="cpu",
        )
    with pytest.raises(ValueError, match="state consumer authority must be null"):
        validate_p1_temporal_consumer_seed_20260612_authority(
            {**authority, "state_consumer_authority": {"gate": "E0-MC"}},
            model_id="P1",
            base_seed=20_260_612,
            device="cpu",
        )


def test_p1_20260613_authority_summary_binds_mj_mk_and_trainer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as sequence_module
    from src.experiments import train_closure_pipe as module

    monkeypatch.setattr(sequence_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    physical_paths = (
        module.SEQUENCE_BUILDER_PATH,
        E0_MJ_LOCK_PATH,
        E0_MJ_MANIFEST_PATH,
        E0_MK_LOCK_PATH,
        E0_MK_MANIFEST_PATH,
        P1_SEQUENCE_20260613_AUDITOR_PATH,
    )
    for relative in physical_paths:
        physical = tmp_path / relative
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_bytes(relative.as_posix().encode("utf-8"))
    builder_record = _file_record(tmp_path / module.SEQUENCE_BUILDER_PATH)
    authority = _p1_20260613_consumer_authority(
        builder_record=builder_record,
        mj_lock_record=_file_record(tmp_path / E0_MJ_LOCK_PATH),
        mj_companion_record=_file_record(tmp_path / E0_MJ_MANIFEST_PATH),
        mk_lock_record=_file_record(tmp_path / E0_MK_LOCK_PATH),
        mk_companion_record=_file_record(tmp_path / E0_MK_MANIFEST_PATH),
        auditor_record=_file_record(tmp_path / P1_SEQUENCE_20260613_AUDITOR_PATH),
    )

    artifact, current, state_context, sequence_inputs, consumer_inputs = (
        validate_p1_temporal_consumer_seed_20260613_authority(
            authority,
            model_id="P1",
            base_seed=20_260_613,
            device="cpu",
        )
    )
    assert artifact == current == builder_record
    assert state_context is None
    assert sequence_inputs == (
        _file_record(tmp_path / E0_MJ_LOCK_PATH),
        _file_record(tmp_path / E0_MJ_MANIFEST_PATH),
    )
    assert consumer_inputs == (
        _file_record(tmp_path / E0_MK_LOCK_PATH),
        _file_record(tmp_path / E0_MK_MANIFEST_PATH),
    )
    assert builder_records_from_p1_seed_20260613_temporal_consumer_authority(
        authority
    ) == (builder_record, builder_record)

    legacy_names = dict(authority)
    legacy_names.pop("historical_mi_effective_loader_called")
    legacy_names.pop("historical_mj_effective_loader_called")
    legacy_names["historical_mg_effective_loader_called"] = False
    legacy_names["historical_mh_effective_loader_called"] = False
    with pytest.raises(ValueError, match="authorization predicates drifted"):
        validate_p1_temporal_consumer_seed_20260613_authority(
            legacy_names,
            model_id="P1",
            base_seed=20_260_613,
            device="cpu",
        )
    with pytest.raises(ValueError, match="authorization predicates drifted"):
        validate_p1_temporal_consumer_seed_20260613_authority(
            {**authority, "p1_20260612_slot_preserved": False},
            model_id="P1",
            base_seed=20_260_613,
            device="cpu",
        )


def test_p1_20260614_authority_summary_binds_ml_mm_and_trainer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as sequence_module
    from src.experiments import train_closure_pipe as module

    monkeypatch.setattr(sequence_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    physical_paths = (
        module.SEQUENCE_BUILDER_PATH,
        E0_ML_LOCK_PATH,
        E0_ML_MANIFEST_PATH,
        E0_MM_LOCK_PATH,
        E0_MM_MANIFEST_PATH,
        P1_SEQUENCE_20260614_AUDITOR_PATH,
    )
    for relative in physical_paths:
        physical = tmp_path / relative
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_bytes(relative.as_posix().encode("utf-8"))
    builder_record = _file_record(tmp_path / module.SEQUENCE_BUILDER_PATH)
    authority = _p1_20260614_consumer_authority(
        builder_record=builder_record,
        ml_lock_record=_file_record(tmp_path / E0_ML_LOCK_PATH),
        ml_companion_record=_file_record(tmp_path / E0_ML_MANIFEST_PATH),
        mm_lock_record=_file_record(tmp_path / E0_MM_LOCK_PATH),
        mm_companion_record=_file_record(tmp_path / E0_MM_MANIFEST_PATH),
        auditor_record=_file_record(tmp_path / P1_SEQUENCE_20260614_AUDITOR_PATH),
    )

    artifact, current, state_context, sequence_inputs, consumer_inputs = (
        validate_p1_temporal_consumer_seed_20260614_authority(
            authority,
            model_id="P1",
            base_seed=20_260_614,
            device="cpu",
        )
    )
    assert artifact == current == builder_record
    assert state_context is None
    assert sequence_inputs == (
        _file_record(tmp_path / E0_ML_LOCK_PATH),
        _file_record(tmp_path / E0_ML_MANIFEST_PATH),
    )
    assert consumer_inputs == (
        _file_record(tmp_path / E0_MM_LOCK_PATH),
        _file_record(tmp_path / E0_MM_MANIFEST_PATH),
    )
    assert builder_records_from_p1_seed_20260614_temporal_consumer_authority(
        authority
    ) == (builder_record, builder_record)

    with pytest.raises(ValueError, match="authorization predicates drifted"):
        validate_p1_temporal_consumer_seed_20260614_authority(
            {**authority, "p1_20260613_slot_preserved": False},
            model_id="P1",
            base_seed=20_260_614,
            device="cpu",
        )
    for model_id, base_seed, device in (
        ("P0", 20_260_614, "cpu"),
        ("P1", 20_260_613, "cpu"),
        ("P1", 20_260_614, "cuda"),
    ):
        with pytest.raises(ValueError, match="only P1 seed 20260614"):
            validate_p1_temporal_consumer_seed_20260614_authority(
                authority,
                model_id=model_id,
                base_seed=base_seed,
                device=device,
            )


def test_p1_314159_authority_summary_binds_mn_mo_and_trainer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as sequence_module
    from src.experiments import train_closure_pipe as module

    monkeypatch.setattr(sequence_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    physical_paths = (
        module.SEQUENCE_BUILDER_PATH,
        E0_MN_LOCK_PATH,
        E0_MN_MANIFEST_PATH,
        E0_MO_LOCK_PATH,
        E0_MO_MANIFEST_PATH,
        P1_SEQUENCE_314159_AUDITOR_PATH,
    )
    for relative in physical_paths:
        physical = tmp_path / relative
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_bytes(relative.as_posix().encode("utf-8"))
    builder_record = _file_record(tmp_path / module.SEQUENCE_BUILDER_PATH)
    authority = _p1_314159_consumer_authority(
        builder_record=builder_record,
        mn_lock_record=_file_record(tmp_path / E0_MN_LOCK_PATH),
        mn_companion_record=_file_record(tmp_path / E0_MN_MANIFEST_PATH),
        mo_lock_record=_file_record(tmp_path / E0_MO_LOCK_PATH),
        mo_companion_record=_file_record(tmp_path / E0_MO_MANIFEST_PATH),
        auditor_record=_file_record(tmp_path / P1_SEQUENCE_314159_AUDITOR_PATH),
    )

    artifact, current, state_context, sequence_inputs, consumer_inputs = (
        validate_p1_temporal_consumer_seed_314159_authority(
            authority,
            model_id="P1",
            base_seed=314_159,
            device="cpu",
        )
    )
    assert artifact == current == builder_record
    assert state_context is None
    assert sequence_inputs == (
        _file_record(tmp_path / E0_MN_LOCK_PATH),
        _file_record(tmp_path / E0_MN_MANIFEST_PATH),
    )
    assert consumer_inputs == (
        _file_record(tmp_path / E0_MO_LOCK_PATH),
        _file_record(tmp_path / E0_MO_MANIFEST_PATH),
    )
    assert builder_records_from_p1_seed_314159_temporal_consumer_authority(
        authority
    ) == (builder_record, builder_record)

    with pytest.raises(ValueError, match="authorization predicates drifted"):
        validate_p1_temporal_consumer_seed_314159_authority(
            {**authority, "p1_20260614_slot_preserved": False},
            model_id="P1",
            base_seed=314_159,
            device="cpu",
        )
    for model_id, base_seed, device in (
        ("P0", 314_159, "cpu"),
        ("P1", 20_260_614, "cpu"),
        ("P1", 314_159, "cuda"),
    ):
        with pytest.raises(ValueError, match="only P1 seed 314159"):
            validate_p1_temporal_consumer_seed_314159_authority(
                authority,
                model_id=model_id,
                base_seed=base_seed,
                device=device,
            )




def test_sequence_identity_must_match_every_common_origin_h1_row() -> None:
    sequences = _sequence_frame()
    common = _common_from_sequences(sequences)
    validate_sequence_common_origin_identity(
        sequences,
        common,
        expected_origin_count=len(sequences),
    )
    common.loc[common["horizon_months"].eq(1), "evaluation_unit_id"] += "-drift"
    with pytest.raises(ValueError, match="identities differ"):
        validate_sequence_common_origin_identity(
            sequences,
            common,
            expected_origin_count=len(sequences),
        )


def test_sequence_input_contract_snapshots_exact_state_and_gate_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as sequence_module
    from src.experiments import train_closure_pipe as training_module

    monkeypatch.setattr(sequence_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(training_module, "PROJECT_ROOT", tmp_path)
    fixed_paths = (
        training_module.DEFAULT_COMMON_ORIGINS,
        training_module.DEFAULT_COMMON_COMPLETION,
        training_module.DEFAULT_RUNTIME_CONFIG,
        training_module.DEFAULT_RUNTIME_SCHEMA,
        training_module.DEFAULT_RUNTIME_LOCK,
        training_module.DEFAULT_ASSIGNMENT,
        training_module.DEFAULT_HOLDOUT_MANIFEST,
        training_module.DEFAULT_PROTOCOL_LOCK,
        Path("src/experiments/build_closure_pipe_sequences.py"),
    )
    for relative in fixed_paths:
        physical = tmp_path / relative
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_bytes(relative.as_posix().encode("utf-8"))
    state_path = tmp_path / "data/state.parquet"
    state_manifest_path = tmp_path / "reports/state_manifest.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_bytes(b"state")
    state_manifest_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        training_module,
        "sequence_paths",
        lambda *_: {
            "state": Path("data/state.parquet"),
            "state_manifest": Path("reports/state_manifest.json"),
        },
    )
    monkeypatch.setattr(
        training_module,
        "validate_state_slot_manifest",
        lambda *args, **kwargs: (True, "", False),
    )

    current_builder = _file_record(
        tmp_path / "src/experiments/build_closure_pipe_sequences.py"
    )
    contract = collect_sequence_input_contract(
        model_id="P0",
        base_seed=1729,
        artifact_builder_record=P0_ARTIFACT_BUILDER_RECORD,
        current_runtime_builder_record=current_builder,
    )
    observed = {str(record["path"]) for record in contract.live_physical_records}
    assert observed == {
        *(path.as_posix() for path in fixed_paths),
        "reports/state_manifest.json",
        "data/state.parquet",
    }
    manifest_by_path = {
        str(record["path"]): record for record in contract.manifest_input_records
    }
    live_by_path = {
        str(record["path"]): record for record in contract.live_physical_records
    }
    builder_path = "src/experiments/build_closure_pipe_sequences.py"
    assert manifest_by_path[builder_path] == P0_ARTIFACT_BUILDER_RECORD
    assert live_by_path[builder_path] == current_builder
    assert manifest_by_path[builder_path] != live_by_path[builder_path]
    assert contract.state_artifact_required is True
    assert_sequence_input_contract_unchanged(contract)
    (tmp_path / training_module.DEFAULT_ASSIGNMENT).write_bytes(b"changed")
    with pytest.raises(ValueError, match="upstream input changed"):
        assert_sequence_input_contract_unchanged(contract)


def test_sequence_input_contract_accepts_published_p1_thirteen_input_dialect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as sequence_module
    from src.experiments import train_closure_pipe as training_module

    monkeypatch.setattr(sequence_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(training_module, "PROJECT_ROOT", tmp_path)
    fixed_paths = (
        training_module.DEFAULT_COMMON_ORIGINS,
        training_module.DEFAULT_COMMON_COMPLETION,
        training_module.DEFAULT_RUNTIME_CONFIG,
        training_module.DEFAULT_RUNTIME_SCHEMA,
        training_module.DEFAULT_RUNTIME_LOCK,
        training_module.DEFAULT_ASSIGNMENT,
        training_module.DEFAULT_HOLDOUT_MANIFEST,
        training_module.DEFAULT_PROTOCOL_LOCK,
        Path("src/experiments/build_closure_pipe_sequences.py"),
        E0_MC_LOCK_PATH,
        E0_MC_MANIFEST_PATH,
    )
    for relative in fixed_paths:
        physical = tmp_path / relative
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_bytes(relative.as_posix().encode("utf-8"))
    state_manifest_path = tmp_path / "reports/state_manifest.json"
    state_path = tmp_path / "data/state.parquet"
    state_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_manifest_path.write_text("{}\n", encoding="utf-8")
    state_path.write_bytes(b"state")
    monkeypatch.setattr(
        training_module,
        "sequence_paths",
        lambda *_: {
            "state": Path("data/state.parquet"),
            "state_manifest": Path("reports/state_manifest.json"),
        },
    )
    observed_authorities: list[object] = []

    def validate_state(*args: object, **kwargs: object) -> tuple[bool, str, bool]:
        observed_authorities.append(kwargs.get("consumer_authority"))
        return True, "", False

    monkeypatch.setattr(training_module, "validate_state_slot_manifest", validate_state)

    current_builder = _file_record(
        tmp_path / "src/experiments/build_closure_pipe_sequences.py"
    )
    contract = collect_sequence_input_contract(
        model_id="P1",
        base_seed=1729,
        artifact_builder_record=current_builder,
        current_runtime_builder_record=current_builder,
        state_consumer_authority={"gate": "E0-MC"},
    )
    assert contract.state_artifact_required is True
    assert len(contract.manifest_input_records) == 13
    assert [str(record["path"]) for record in contract.manifest_input_records][-4:] == [
        "reports/state_manifest.json",
        E0_MC_LOCK_PATH.as_posix(),
        E0_MC_MANIFEST_PATH.as_posix(),
        "data/state.parquet",
    ]
    assert contract.manifest_input_records == contract.live_physical_records
    assert observed_authorities == [{"gate": "E0-MC"}]
    state_path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="upstream input changed"):
        assert_sequence_input_contract_unchanged(contract)


def test_sequence_input_contract_accepts_seed_20260612_mh_input_dialect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as sequence_module
    from src.experiments import train_closure_pipe as module

    monkeypatch.setattr(sequence_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    fixed_paths = (
        module.DEFAULT_COMMON_ORIGINS,
        module.DEFAULT_COMMON_COMPLETION,
        module.DEFAULT_RUNTIME_CONFIG,
        module.DEFAULT_RUNTIME_SCHEMA,
        module.DEFAULT_RUNTIME_LOCK,
        module.DEFAULT_ASSIGNMENT,
        module.DEFAULT_HOLDOUT_MANIFEST,
        module.DEFAULT_PROTOCOL_LOCK,
        module.SEQUENCE_BUILDER_PATH,
    )
    state_manifest_path = Path(
        "reports/closure_v1/01_surface/anfis/seed_20260612/manifest.json"
    )
    state_path = Path(
        "data/closure_v1/development/anfis/seed_20260612/"
        "adaptive_no_current_state.parquet"
    )
    for relative in (
        *fixed_paths,
        state_manifest_path,
        E0_MH_LOCK_PATH,
        E0_MH_MANIFEST_PATH,
        state_path,
    ):
        physical = tmp_path / relative
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_bytes(relative.as_posix().encode("utf-8"))
    (tmp_path / state_manifest_path).write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        module,
        "sequence_paths",
        lambda *_: {"state": state_path, "state_manifest": state_manifest_path},
    )
    observed_authorities: list[object] = []

    def validate_state(*args: object, **kwargs: object) -> tuple[bool, str, bool]:
        observed_authorities.append(kwargs.get("consumer_authority"))
        return True, "", False

    monkeypatch.setattr(module, "validate_state_slot_manifest", validate_state)
    builder_record = _file_record(tmp_path / module.SEQUENCE_BUILDER_PATH)
    sequence_authorities = (
        _file_record(tmp_path / E0_MH_LOCK_PATH),
        _file_record(tmp_path / E0_MH_MANIFEST_PATH),
    )
    contract = collect_sequence_input_contract(
        model_id="P1",
        base_seed=20_260_612,
        artifact_builder_record=builder_record,
        current_runtime_builder_record=builder_record,
        state_consumer_authority=None,
        sequence_authority_input_records=sequence_authorities,
    )
    assert [str(record["path"]) for record in contract.manifest_input_records] == [
        *(path.as_posix() for path in fixed_paths),
        state_manifest_path.as_posix(),
        E0_MH_LOCK_PATH.as_posix(),
        E0_MH_MANIFEST_PATH.as_posix(),
        state_path.as_posix(),
    ]
    assert E0_MC_LOCK_PATH.as_posix() not in {
        str(record["path"]) for record in contract.manifest_input_records
    }
    assert contract.manifest_input_records == contract.live_physical_records
    assert observed_authorities == [None]


def test_temporal_model_contract_tracks_dltv_and_dltvm_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as sequence_module
    from src.experiments import train_closure_pipe as training_module

    monkeypatch.setattr(sequence_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(training_module, "PROJECT_ROOT", tmp_path)
    sequence_files = {
        "sequence": Path("data/sequence.parquet"),
        "summary": Path("reports/sequence_summary.csv"),
        "manifest": Path("reports/sequence_manifest.json"),
    }
    monkeypatch.setattr(training_module, "sequence_paths", lambda *_: sequence_files)
    source_paths = (
        "src/experiments/train_closure_pipe.py",
        "src/experiments/build_closure_pipe_sequences.py",
        "src/experiments/closure_contract.py",
        "src/experiments/closure_development_guard.py",
        "src/experiments/closure_development_runtime_lock.py",
        "src/experiments/closure_development_runtime_temporal_consumer_patch.py",
        "src/experiments/closure_development_runtime_temporal_validation_patch.py",
        "src/experiments/closure_development_runtime_temporal_validation_manifest_patch.py",
        "src/experiments/closure_runtime_contract.py",
        "src/experiments/train_pipe_grud.py",
    )
    for relative in (*sequence_files.values(), *(Path(path) for path in source_paths)):
        physical = tmp_path / relative
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_bytes(relative.as_posix().encode("utf-8"))

    sequence_contract = SequenceInputContract(
        manifest_input_records=(),
        live_physical_records=(),
        state_path=tmp_path / "data/absent_state.parquet",
        state_artifact_required=False,
    )
    contract = training_module.collect_temporal_model_input_contract(
        model_id="P0",
        base_seed=1729,
        sequence_contract=sequence_contract,
    )

    observed_sources = {str(record["path"]) for record in contract.source_code_records}
    assert observed_sources == set(source_paths)
    assert {
        "src/experiments/closure_development_runtime_temporal_validation_patch.py",
        "src/experiments/closure_development_runtime_temporal_validation_manifest_patch.py",
    }.issubset(observed_sources)


def test_p1_temporal_model_contract_tracks_historical_sources_and_dynamic_pointer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as sequence_module
    from src.experiments import train_closure_pipe as training_module

    monkeypatch.setattr(sequence_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(training_module, "PROJECT_ROOT", tmp_path)
    sequence_files = {
        "sequence": Path("data/sequence.parquet"),
        "summary": Path("reports/sequence_summary.csv"),
        "manifest": Path("reports/sequence_manifest.json"),
    }
    monkeypatch.setattr(training_module, "sequence_paths", lambda *_: sequence_files)
    common_sources = (
        Path("src/experiments/train_closure_pipe.py"),
        Path("src/experiments/build_closure_pipe_sequences.py"),
        Path("src/experiments/closure_contract.py"),
        Path("src/experiments/closure_development_guard.py"),
        Path("src/experiments/closure_development_runtime_lock.py"),
        Path("src/experiments/closure_development_runtime_temporal_consumer_patch.py"),
        Path("src/experiments/closure_development_runtime_temporal_validation_patch.py"),
        Path(
            "src/experiments/"
            "closure_development_runtime_temporal_validation_manifest_patch.py"
        ),
        Path("src/experiments/closure_runtime_contract.py"),
        Path("src/experiments/train_pipe_grud.py"),
    )
    p1_sources = (
        E0_MC_AUTHORITY_PATH,
        P1_SEQUENCE_AUDITOR_PATH,
        E0_MD_GATE_PATH,
        E0_ME_GATE_PATH,
        E0_MF_GATE_PATH,
        E0_MG_GATE_PATH,
    )
    dependency_paths = (
        *sequence_files.values(),
        Path("data/sequence.parquet.dvc"),
        E0_MG_LOCK_PATH,
        E0_MG_MANIFEST_PATH,
        *common_sources,
        *p1_sources,
    )
    for relative in dependency_paths:
        physical = tmp_path / relative
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_bytes(relative.as_posix().encode("utf-8"))

    sequence_contract = SequenceInputContract(
        manifest_input_records=(),
        live_physical_records=(),
        state_path=tmp_path / "data/absent_state.parquet",
        state_artifact_required=False,
    )
    contract = training_module.collect_temporal_model_input_contract(
        model_id="P1",
        base_seed=1729,
        sequence_contract=sequence_contract,
        authority_input_records=(
            _file_record(tmp_path / E0_MG_LOCK_PATH),
            _file_record(tmp_path / E0_MG_MANIFEST_PATH),
        ),
    )

    observed = {str(record["path"]) for record in contract.records}
    observed_sources = {str(record["path"]) for record in contract.source_code_records}
    assert {path.as_posix() for path in dependency_paths}.issubset(observed)
    assert observed_sources == {
        *(path.as_posix() for path in common_sources),
        *(path.as_posix() for path in p1_sources),
    }


def test_p1_20260612_model_contract_uses_dynamic_pointer_and_mi_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as sequence_module
    from src.experiments import train_closure_pipe as module

    monkeypatch.setattr(sequence_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    sequence_files = {
        "sequence": Path(
            "data/closure_v1/development/sequences/P1/seed_20260612.parquet"
        ),
        "summary": Path(
            "reports/closure_v1/01_surface/sequences/P1/"
            "seed_20260612_summary.csv"
        ),
        "manifest": Path(
            "reports/closure_v1/01_surface/sequences/P1/"
            "seed_20260612_manifest.json"
        ),
    }
    monkeypatch.setattr(module, "sequence_paths", lambda *_: sequence_files)
    common_sources = (
        Path("src/experiments/train_closure_pipe.py"),
        Path("src/experiments/build_closure_pipe_sequences.py"),
        Path("src/experiments/closure_contract.py"),
        Path("src/experiments/closure_development_guard.py"),
        Path("src/experiments/closure_development_runtime_lock.py"),
        Path("src/experiments/closure_development_runtime_temporal_consumer_patch.py"),
        Path("src/experiments/closure_development_runtime_temporal_validation_patch.py"),
        Path(
            "src/experiments/"
            "closure_development_runtime_temporal_validation_manifest_patch.py"
        ),
        Path("src/experiments/closure_runtime_contract.py"),
        Path("src/experiments/train_pipe_grud.py"),
    )
    pointer = Path(f"{sequence_files['sequence'].as_posix()}.dvc")
    for relative in (
        *sequence_files.values(),
        pointer,
        *common_sources,
        *P1_20260612_AUTHORITY_SOURCE_PATHS,
        E0_MH_LOCK_PATH,
        E0_MH_MANIFEST_PATH,
        E0_MI_LOCK_PATH,
        E0_MI_MANIFEST_PATH,
    ):
        physical = tmp_path / relative
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_bytes(relative.as_posix().encode("utf-8"))
    sequence_contract = SequenceInputContract(
        manifest_input_records=(),
        live_physical_records=(
            _file_record(tmp_path / E0_MH_LOCK_PATH),
            _file_record(tmp_path / E0_MH_MANIFEST_PATH),
        ),
        state_path=tmp_path / "data/absent-state.parquet",
        state_artifact_required=False,
    )
    contract = module.collect_temporal_model_input_contract(
        model_id="P1",
        base_seed=20_260_612,
        sequence_contract=sequence_contract,
        authority_input_records=(
            _file_record(tmp_path / E0_MI_LOCK_PATH),
            _file_record(tmp_path / E0_MI_MANIFEST_PATH),
        ),
        p1_authority_source_paths=P1_20260612_AUTHORITY_SOURCE_PATHS,
    )
    observed = {str(record["path"]) for record in contract.records}
    observed_sources = [str(record["path"]) for record in contract.source_code_records]
    assert pointer == P1_SEQUENCE_20260612_POINTER_PATH
    assert pointer.as_posix() in observed
    assert P1_SEQUENCE_POINTER_PATH.as_posix() not in observed
    assert observed_sources == [
        *(path.as_posix() for path in common_sources),
        *(path.as_posix() for path in P1_20260612_AUTHORITY_SOURCE_PATHS),
    ]
    assert len(observed_sources) == 19
    assert E0_MI_LOCK_PATH.as_posix() in observed
    assert E0_MH_LOCK_PATH.as_posix() in observed


def test_p1_20260614_model_contract_uses_dynamic_pointer_and_mm_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as sequence_module
    from src.experiments import train_closure_pipe as module

    monkeypatch.setattr(sequence_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    sequence_files = {
        "sequence": Path(
            "data/closure_v1/development/sequences/P1/seed_20260614.parquet"
        ),
        "summary": Path(
            "reports/closure_v1/01_surface/sequences/P1/"
            "seed_20260614_summary.csv"
        ),
        "manifest": Path(
            "reports/closure_v1/01_surface/sequences/P1/"
            "seed_20260614_manifest.json"
        ),
    }
    monkeypatch.setattr(module, "sequence_paths", lambda *_: sequence_files)
    common_sources = (
        Path("src/experiments/train_closure_pipe.py"),
        Path("src/experiments/build_closure_pipe_sequences.py"),
        Path("src/experiments/closure_contract.py"),
        Path("src/experiments/closure_development_guard.py"),
        Path("src/experiments/closure_development_runtime_lock.py"),
        Path("src/experiments/closure_development_runtime_temporal_consumer_patch.py"),
        Path("src/experiments/closure_development_runtime_temporal_validation_patch.py"),
        Path(
            "src/experiments/"
            "closure_development_runtime_temporal_validation_manifest_patch.py"
        ),
        Path("src/experiments/closure_runtime_contract.py"),
        Path("src/experiments/train_pipe_grud.py"),
    )
    pointer = Path(f"{sequence_files['sequence'].as_posix()}.dvc")
    for relative in (
        *sequence_files.values(),
        pointer,
        *common_sources,
        *P1_20260614_AUTHORITY_SOURCE_PATHS,
        E0_ML_LOCK_PATH,
        E0_ML_MANIFEST_PATH,
        E0_MM_LOCK_PATH,
        E0_MM_MANIFEST_PATH,
    ):
        physical = tmp_path / relative
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_bytes(relative.as_posix().encode("utf-8"))
    sequence_contract = SequenceInputContract(
        manifest_input_records=(),
        live_physical_records=(
            _file_record(tmp_path / E0_ML_LOCK_PATH),
            _file_record(tmp_path / E0_ML_MANIFEST_PATH),
        ),
        state_path=tmp_path / "data/absent-state.parquet",
        state_artifact_required=False,
    )
    contract = module.collect_temporal_model_input_contract(
        model_id="P1",
        base_seed=20_260_614,
        sequence_contract=sequence_contract,
        authority_input_records=(
            _file_record(tmp_path / E0_MM_LOCK_PATH),
            _file_record(tmp_path / E0_MM_MANIFEST_PATH),
        ),
        p1_authority_source_paths=P1_20260614_AUTHORITY_SOURCE_PATHS,
    )
    observed = {str(record["path"]) for record in contract.records}
    observed_sources = [str(record["path"]) for record in contract.source_code_records]
    assert pointer == P1_SEQUENCE_20260614_POINTER_PATH
    assert pointer.as_posix() in observed
    assert P1_SEQUENCE_20260613_POINTER_PATH.as_posix() not in observed
    assert observed_sources == [
        *(path.as_posix() for path in common_sources),
        *(path.as_posix() for path in P1_20260614_AUTHORITY_SOURCE_PATHS),
    ]
    assert E0_MM_LOCK_PATH.as_posix() in observed
    assert E0_ML_LOCK_PATH.as_posix() in observed


def test_p1_314159_model_contract_uses_dynamic_pointer_and_mo_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as sequence_module
    from src.experiments import train_closure_pipe as module

    monkeypatch.setattr(sequence_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    sequence_files = {
        "sequence": Path(
            "data/closure_v1/development/sequences/P1/seed_314159.parquet"
        ),
        "summary": Path(
            "reports/closure_v1/01_surface/sequences/P1/"
            "seed_314159_summary.csv"
        ),
        "manifest": Path(
            "reports/closure_v1/01_surface/sequences/P1/"
            "seed_314159_manifest.json"
        ),
    }
    monkeypatch.setattr(module, "sequence_paths", lambda *_: sequence_files)
    common_sources = (
        Path("src/experiments/train_closure_pipe.py"),
        Path("src/experiments/build_closure_pipe_sequences.py"),
        Path("src/experiments/closure_contract.py"),
        Path("src/experiments/closure_development_guard.py"),
        Path("src/experiments/closure_development_runtime_lock.py"),
        Path("src/experiments/closure_development_runtime_temporal_consumer_patch.py"),
        Path("src/experiments/closure_development_runtime_temporal_validation_patch.py"),
        Path(
            "src/experiments/"
            "closure_development_runtime_temporal_validation_manifest_patch.py"
        ),
        Path("src/experiments/closure_runtime_contract.py"),
        Path("src/experiments/train_pipe_grud.py"),
    )
    pointer = Path(f"{sequence_files['sequence'].as_posix()}.dvc")
    for relative in (
        *sequence_files.values(),
        pointer,
        *common_sources,
        *P1_314159_AUTHORITY_SOURCE_PATHS,
        E0_MN_LOCK_PATH,
        E0_MN_MANIFEST_PATH,
        E0_MO_LOCK_PATH,
        E0_MO_MANIFEST_PATH,
    ):
        physical = tmp_path / relative
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_bytes(relative.as_posix().encode("utf-8"))
    sequence_contract = SequenceInputContract(
        manifest_input_records=(),
        live_physical_records=(
            _file_record(tmp_path / E0_MN_LOCK_PATH),
            _file_record(tmp_path / E0_MN_MANIFEST_PATH),
        ),
        state_path=tmp_path / "data/absent-state.parquet",
        state_artifact_required=False,
    )
    contract = module.collect_temporal_model_input_contract(
        model_id="P1",
        base_seed=314_159,
        sequence_contract=sequence_contract,
        authority_input_records=(
            _file_record(tmp_path / E0_MO_LOCK_PATH),
            _file_record(tmp_path / E0_MO_MANIFEST_PATH),
        ),
        p1_authority_source_paths=P1_314159_AUTHORITY_SOURCE_PATHS,
    )
    observed = {str(record["path"]) for record in contract.records}
    observed_sources = [str(record["path"]) for record in contract.source_code_records]
    assert pointer == P1_SEQUENCE_314159_POINTER_PATH
    assert pointer.as_posix() in observed
    assert P1_SEQUENCE_20260614_POINTER_PATH.as_posix() not in observed
    assert observed_sources == [
        *(path.as_posix() for path in common_sources),
        *(path.as_posix() for path in P1_314159_AUTHORITY_SOURCE_PATHS),
    ]
    assert E0_MO_LOCK_PATH.as_posix() in observed
    assert E0_MN_LOCK_PATH.as_posix() in observed




def test_unavailable_slot_rejects_stale_fit_outputs(tmp_path: Path) -> None:
    fields = (
        "model",
        "checkpoint",
        "preprocessor",
        "metrics",
        "training_curve",
        "blend_weights",
        "blend_search",
        "report",
        "manifest",
    )
    paths = {field: tmp_path / f"{field}.artifact" for field in fields}
    paths["model"].write_bytes(b"stale")

    with pytest.raises(ValueError, match="stale fit outputs"):
        _write_model_unavailable_evidence(
            model_id="P1",
            base_seed=1729,
            device="cpu",
            paths=paths,
            input_records=[],
            source_code_records=[],
            cpu_execution_policy=expected_cpu_execution_policy_record(),
            failure_reason="sequence_fit_rows_unavailable",
            fit_status_counts={"model_slot_unavailable": 8352},
            failure_reason_counts={"anfis_model_slot_unavailable": 8352},
        )
    assert not paths["manifest"].exists()


def _temporal_test_paths(tmp_path: Path) -> dict[str, Path]:
    return {
        field: tmp_path / "slot" / f"{field}.artifact"
        for field in (*MODEL_ARTIFACT_OUTPUT_NAMES, "manifest")
    }


def test_unavailable_slot_publishes_report_then_bound_manifest_without_fit_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.experiments import train_closure_pipe as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    paths = _temporal_test_paths(tmp_path)

    _write_model_unavailable_evidence(
        model_id="P0",
        base_seed=1729,
        device="cpu",
        paths=paths,
        input_records=[],
        source_code_records=[],
        cpu_execution_policy=expected_cpu_execution_policy_record(),
        failure_reason="sequence_fit_rows_unavailable",
        fit_status_counts={"autoregressive_target_unavailable": 488},
        failure_reason_counts={"missing_target_state": 488},
    )

    assert paths["report"].read_text(encoding="utf-8").endswith(
        "the failed slot was not replaced.\n"
    )
    payload = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    assert payload["slot_status"] == "model_unavailable"
    assert payload["fit_status"] == "not_attempted"
    assert payload["failure_reason"] == "sequence_fit_rows_unavailable"
    assert payload["model_artifact_emitted"] is False
    assert payload["outputs"] == [
        {
            "path": paths["report"].as_posix(),
            "bytes": paths["report"].stat().st_size,
            "sha256": hashlib.sha256(paths["report"].read_bytes()).hexdigest(),
            "artifact_role": "report",
        }
    ]
    for name, path in paths.items():
        assert _path_entry_exists(path) is (name in {"report", "manifest"})
        assert not _path_entry_exists(path.with_suffix(path.suffix + ".tmp"))


def test_unavailable_slot_rolls_back_report_when_manifest_publication_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.experiments import train_closure_pipe as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    paths = _temporal_test_paths(tmp_path)
    real_publish_json = _TemporalOutputTransaction.publish_json
    fail_once = True

    def fail_manifest(
        self: _TemporalOutputTransaction,
        payload: Mapping[str, Any],
        path: Path,
    ) -> None:
        nonlocal fail_once
        if fail_once:
            fail_once = False
            raise RuntimeError("injected manifest failure")
        real_publish_json(self, payload, path)

    monkeypatch.setattr(_TemporalOutputTransaction, "publish_json", fail_manifest)
    with pytest.raises(RuntimeError, match="injected manifest failure"):
        _write_model_unavailable_evidence(
            model_id="P0",
            base_seed=1729,
            device="cpu",
            paths=paths,
            input_records=[],
            source_code_records=[],
            cpu_execution_policy=expected_cpu_execution_policy_record(),
            failure_reason="sequence_fit_rows_unavailable",
            fit_status_counts={"autoregressive_target_unavailable": 488},
            failure_reason_counts={"missing_target_state": 488},
        )

    for path in paths.values():
        assert not _path_entry_exists(path)
        assert not _path_entry_exists(path.with_suffix(path.suffix + ".tmp"))

    _write_model_unavailable_evidence(
        model_id="P0",
        base_seed=1729,
        device="cpu",
        paths=paths,
        input_records=[],
        source_code_records=[],
        cpu_execution_policy=expected_cpu_execution_policy_record(),
        failure_reason="sequence_fit_rows_unavailable",
        fit_status_counts={"autoregressive_target_unavailable": 488},
        failure_reason_counts={"missing_target_state": 488},
    )
    assert paths["report"].is_file()
    assert paths["manifest"].is_file()


def test_temporal_transaction_rolls_back_owned_outputs_but_preserves_replacement(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.experiments import train_closure_pipe as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    first = tmp_path / "slot" / "first.txt"
    second = tmp_path / "slot" / "second.txt"
    with pytest.raises(RuntimeError, match="injected failure"):
        with _TemporalOutputTransaction() as transaction:
            transaction.publish_text("owned", first)
            transaction.publish_text("also-owned", second)
            first.unlink()
            first.write_text("replacement", encoding="utf-8")
            raise RuntimeError("injected failure")

    assert first.read_text(encoding="utf-8") == "replacement"
    assert not _path_entry_exists(second)
    assert not _path_entry_exists(first.with_suffix(".txt.tmp"))
    assert not _path_entry_exists(second.with_suffix(".txt.tmp"))


def test_temporal_transaction_attempts_every_rollback_after_fsync_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.experiments import train_closure_pipe as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    first = tmp_path / "slot" / "first.txt"
    second = tmp_path / "slot" / "second.txt"
    real_fsync = os.fsync
    state = {"rollback": False, "failed_calls": 0}

    def controlled_fsync(descriptor: int) -> None:
        if state["rollback"]:
            state["failed_calls"] += 1
            raise OSError("injected fsync failure")
        real_fsync(descriptor)

    monkeypatch.setattr(module.os, "fsync", controlled_fsync)
    with pytest.raises(ValueError, match="rollback could not be completed safely") as raised:
        with _TemporalOutputTransaction() as transaction:
            transaction.publish_text("first", first)
            transaction.publish_text("second", second)
            state["rollback"] = True
            raise RuntimeError("trigger rollback")

    assert state["failed_calls"] == 2
    assert not _path_entry_exists(first)
    assert not _path_entry_exists(second)
    assert raised.value.__notes__ == [
        "Rollback failures: OSError: injected fsync failure; "
        "OSError: injected fsync failure"
    ]


def test_temporal_transaction_refuses_existing_final_without_clobber(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.experiments import train_closure_pipe as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    target = tmp_path / "slot" / "artifact.txt"
    target.parent.mkdir(parents=True)
    target.write_text("racer", encoding="utf-8")

    with pytest.raises(ValueError, match="Refusing to overwrite final artifact"):
        with _TemporalOutputTransaction() as transaction:
            transaction.publish_text("ours", target)

    assert target.read_text(encoding="utf-8") == "racer"
    assert not _path_entry_exists(target.with_suffix(".txt.tmp"))


def test_temporal_transaction_fails_closed_if_temporary_inode_is_replaced(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.experiments import train_closure_pipe as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    target = tmp_path / "slot" / "artifact.txt"
    temporary = target.with_suffix(".txt.tmp")
    real_link = os.link

    def replace_temporary_after_link(*args: Any, **kwargs: Any) -> None:
        real_link(*args, **kwargs)
        temporary.unlink()
        temporary.write_text("foreign", encoding="utf-8")

    monkeypatch.setattr(module.os, "link", replace_temporary_after_link)
    with pytest.raises(ValueError, match="Temporary artifact changed before cleanup"):
        with _TemporalOutputTransaction() as transaction:
            transaction.publish_text("owned", target)

    assert not _path_entry_exists(target)
    assert temporary.read_text(encoding="utf-8") == "foreign"


def test_temporal_transaction_fails_commit_if_owned_final_is_replaced(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.experiments import train_closure_pipe as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    target = tmp_path / "slot" / "artifact.txt"
    with pytest.raises(ValueError, match="identity drifted before commit"):
        with _TemporalOutputTransaction() as transaction:
            transaction.publish_text("owned", target)
            target.unlink()
            target.write_text("replacement", encoding="utf-8")

    assert target.read_text(encoding="utf-8") == "replacement"
    assert not _path_entry_exists(target.with_suffix(".txt.tmp"))


def test_temporal_transaction_rejects_symlinked_output_ancestor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.experiments import train_closure_pipe as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)

    with pytest.raises(ValueError, match="ancestor is not a real directory"):
        with _TemporalOutputTransaction() as transaction:
            transaction.publish_text("forbidden", linked_parent / "artifact.txt")
    assert list(real_parent.iterdir()) == []


def test_output_parent_walk_closes_child_and_parent_once_when_child_fstat_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.experiments import train_closure_pipe as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    real_open = os.open
    real_close = os.close
    real_fstat = os.fstat
    opened: list[int] = []
    closed: list[int] = []

    def tracked_open(*args: Any, **kwargs: Any) -> int:
        descriptor = real_open(*args, **kwargs)
        opened.append(descriptor)
        return descriptor

    def fail_child_fstat(descriptor: int) -> os.stat_result:
        if len(opened) == 2 and descriptor == opened[-1]:
            raise OSError("injected child fstat failure")
        return real_fstat(descriptor)

    def tracked_close(descriptor: int) -> None:
        closed.append(descriptor)
        real_close(descriptor)

    monkeypatch.setattr(module.os, "open", tracked_open)
    monkeypatch.setattr(module.os, "fstat", fail_child_fstat)
    monkeypatch.setattr(module.os, "close", tracked_close)
    with pytest.raises(OSError, match="injected child fstat failure"):
        _open_real_output_parent(tmp_path / "slot/artifact.txt")

    assert len(opened) == 2
    assert {descriptor: closed.count(descriptor) for descriptor in opened} == {
        descriptor: 1 for descriptor in opened
    }


def test_temporal_writer_closes_duplicate_when_fdopen_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.experiments import train_closure_pipe as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    real_dup = os.dup
    real_close = os.close
    duplicates: list[int] = []
    closed: list[int] = []

    def tracked_dup(descriptor: int) -> int:
        duplicate = real_dup(descriptor)
        duplicates.append(duplicate)
        return duplicate

    def fail_fdopen(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("injected fdopen failure")

    def tracked_close(descriptor: int) -> None:
        closed.append(descriptor)
        real_close(descriptor)

    monkeypatch.setattr(module.os, "dup", tracked_dup)
    monkeypatch.setattr(module.os, "fdopen", fail_fdopen)
    monkeypatch.setattr(module.os, "close", tracked_close)
    target = tmp_path / "slot/artifact.txt"
    with pytest.raises(RuntimeError, match="injected fdopen failure"):
        with _TemporalOutputTransaction() as transaction:
            transaction.publish_text("payload", target)

    assert len(duplicates) == 1
    assert closed.count(duplicates[0]) == 1
    assert not _path_entry_exists(target)
    assert not _path_entry_exists(target.with_suffix(".txt.tmp"))


def test_temporal_writer_never_retries_close_and_fsyncs_local_rollback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.experiments import train_closure_pipe as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    real_open = os.open
    real_close = os.close
    real_fsync = os.fsync
    temporary_descriptor: int | None = None
    temporary_close_calls = 0
    fsync_calls = 0

    def tracked_open(path: Any, *args: Any, **kwargs: Any) -> int:
        nonlocal temporary_descriptor
        descriptor = real_open(path, *args, **kwargs)
        if str(path).endswith("artifact.txt.tmp"):
            temporary_descriptor = descriptor
        return descriptor

    def fail_close_once(descriptor: int) -> None:
        nonlocal temporary_close_calls
        if descriptor == temporary_descriptor:
            temporary_close_calls += 1
            real_close(descriptor)
            raise OSError("injected close failure")
        real_close(descriptor)

    def tracked_fsync(descriptor: int) -> None:
        nonlocal fsync_calls
        fsync_calls += 1
        real_fsync(descriptor)

    monkeypatch.setattr(module.os, "open", tracked_open)
    monkeypatch.setattr(module.os, "close", fail_close_once)
    monkeypatch.setattr(module.os, "fsync", tracked_fsync)
    target = tmp_path / "slot/artifact.txt"
    with pytest.raises(OSError, match="injected close failure"):
        with _TemporalOutputTransaction() as transaction:
            transaction.publish_text("payload", target)

    assert temporary_descriptor is not None
    assert temporary_close_calls == 1
    assert fsync_calls >= 3
    assert not _path_entry_exists(target)
    assert not _path_entry_exists(target.with_suffix(".txt.tmp"))


def test_temporal_slot_preflight_forbids_partial_or_completed_resume(
    tmp_path: Path,
) -> None:
    fields = (*MODEL_ARTIFACT_OUTPUT_NAMES, "manifest")
    paths = {field: tmp_path / f"{field}.artifact" for field in fields}
    assert_temporal_slot_outputs_absent(paths)

    paths["report"].write_bytes(b"partial")
    with pytest.raises(ValueError, match="resume/overwrite is forbidden"):
        assert_temporal_slot_outputs_absent(paths)

    paths["report"].unlink()
    paths["manifest"].write_bytes(b"completed")
    with pytest.raises(ValueError, match="resume/overwrite is forbidden"):
        assert_temporal_slot_outputs_absent(paths)

    paths["manifest"].unlink()
    temporary = paths["model"].with_suffix(paths["model"].suffix + ".tmp")
    temporary.write_bytes(b"interrupted")
    with pytest.raises(ValueError, match="resume/overwrite is forbidden"):
        assert_temporal_slot_outputs_absent(paths)


def test_temporal_slot_preflight_detects_broken_symlink_and_fifo(tmp_path: Path) -> None:
    paths = _temporal_test_paths(tmp_path)
    paths["report"].parent.mkdir(parents=True)
    paths["report"].symlink_to(tmp_path / "missing-target")
    assert not paths["report"].exists()
    with pytest.raises(ValueError, match="resume/overwrite is forbidden"):
        assert_temporal_slot_outputs_absent(paths)

    paths["report"].unlink()
    os.mkfifo(paths["report"])
    with pytest.raises(ValueError, match="resume/overwrite is forbidden"):
        assert_temporal_slot_outputs_absent(paths)


def test_temporal_slot_guard_is_exclusive_and_releases_only_its_inode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.experiments import train_closure_pipe as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    guard = tmp_path / "tmp/closure_v1_temporal_consumer/P0_seed_1729.guard"
    with _temporal_slot_guard("P0", 1729):
        assert guard.is_file()
        with pytest.raises(ValueError, match="already reserved"):
            with _temporal_slot_guard("P0", 1729):
                pass
    assert not guard.exists()

    with pytest.raises(ValueError, match="guard changed"):
        with _temporal_slot_guard("P0", 1729):
            guard.unlink()
            guard.write_text("replacement", encoding="utf-8")
    assert guard.read_text(encoding="utf-8") == "replacement"


def test_temporal_slot_guard_rejects_symlinked_tmp_ancestor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.experiments import train_closure_pipe as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    redirected = tmp_path / "redirected"
    redirected.mkdir()
    (tmp_path / "tmp").symlink_to(redirected, target_is_directory=True)

    with pytest.raises(ValueError, match="ancestor is not a real directory"):
        with _temporal_slot_guard("P0", 1729):
            pass
    assert list(redirected.iterdir()) == []


def test_run_p1_temporal_slot_emits_only_unavailable_evidence_and_never_fits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.experiments import build_closure_pipe_sequences as sequence_module
    from src.experiments import train_closure_pipe as module

    monkeypatch.setattr(sequence_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    sequence = tmp_path / "inputs/sequence.parquet"
    summary = tmp_path / "inputs/summary.csv"
    sequence_manifest = tmp_path / "inputs/manifest.json"
    common = tmp_path / module.DEFAULT_COMMON_ORIGINS
    builder = tmp_path / module.SEQUENCE_BUILDER_PATH
    mh_lock = tmp_path / E0_MH_LOCK_PATH
    mh_companion = tmp_path / E0_MH_MANIFEST_PATH
    mi_lock = tmp_path / E0_MI_LOCK_PATH
    mi_companion = tmp_path / E0_MI_MANIFEST_PATH
    auditor = tmp_path / P1_SEQUENCE_20260612_AUDITOR_PATH
    for path, payload in (
        (sequence, b"sequence"),
        (summary, b"summary"),
        (common, b"common"),
        (builder, b"current-runtime-builder"),
        (mh_lock, b"mh-lock"),
        (mh_companion, b"mh-companion"),
        (mi_lock, b"mi-lock"),
        (mi_companion, b"mi-companion"),
        (auditor, b"read-only-auditor"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    sequence_record = _file_record(sequence)
    summary_record = _file_record(summary)
    common_record = _file_record(common)
    current_builder_record = _file_record(builder)
    manifest_inputs = (current_builder_record, common_record)
    sequence_manifest.write_text(
        json.dumps(
            {
                "manifest_version": "closure_pipe_sequence_manifest_v1",
                "status": "completed",
                "generated_at_utc": "2026-08-04T17:44:49+00:00",
                "experiment_id": "closure_v1",
                "surface_id": SURFACE_ID,
                "model_id": "P1",
                "base_seed": 20_260_612,
                "future_outcomes_accessed": False,
                "evaluation_authorized": False,
                "e0_u_authorized": False,
                "script": current_builder_record,
                "cpu_execution_policy": expected_cpu_execution_policy_record(),
                "input_state_mapping": MODEL_STATE_MAPPINGS["P1"],
                "target_state_mapping": MODEL_STATE_MAPPINGS["P1"],
                "target_to_next_input_mapping": TARGET_TO_NEXT_INPUT_MAPPING,
                "input_columns": list(INPUT_COLUMNS),
                "target_columns": list(TARGET_COLUMNS),
                "optional_context_columns": [],
                "serialization": {
                    "rows_per_common_origin": 1,
                    "input_physical_type": "fixed_size_list<float32>[12]",
                    "target_physical_type": "float32",
                    "canonical_order": [
                        "source_id",
                        "site_id",
                        "origin_year_month",
                        "target_year_month",
                    ],
                },
                "counts": {
                    "intent_origins": 9732,
                    "role_counts": {
                        "training": 8352,
                        "model_selection": 1061,
                        "calibration_threshold": 319,
                    },
                },
                "inputs": [dict(record) for record in manifest_inputs],
                "source_code": [current_builder_record],
                "outputs": [sequence_record, summary_record],
                "completion_marker_written_last": True,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest_record = _file_record(sequence_manifest)
    sequence_contract = SequenceInputContract(
        manifest_input_records=manifest_inputs,
        live_physical_records=(current_builder_record, common_record),
        state_path=tmp_path / "inputs/unavailable-state.parquet",
        state_artifact_required=False,
    )
    model_contract = TemporalModelInputContract(
        records=(
            sequence_record,
            summary_record,
            manifest_record,
            common_record,
            current_builder_record,
        ),
        source_code_records=(),
        sequence_contract=sequence_contract,
    )
    monkeypatch.setattr(module, "load_yaml_mapping", lambda path: {})
    monkeypatch.setattr(module, "validate_temporal_runtime_contract", lambda runtime: None)
    monkeypatch.setattr(
        module,
        "configure_torch_cpu_execution_policy",
        lambda runtime: expected_cpu_execution_policy_record(),
    )
    monkeypatch.setattr(
        module,
        "sequence_paths",
        lambda model_id, base_seed: {
            "sequence": sequence.relative_to(tmp_path),
            "summary": summary.relative_to(tmp_path),
            "manifest": sequence_manifest.relative_to(tmp_path),
        },
    )
    monkeypatch.setattr(
        module,
        "collect_sequence_input_contract",
        lambda **kwargs: sequence_contract,
    )
    monkeypatch.setattr(
        module,
        "collect_temporal_model_input_contract",
        lambda **kwargs: model_contract,
    )
    monkeypatch.setattr(module.pq, "read_schema", lambda path: object())
    monkeypatch.setattr(module, "validate_sequence_physical_schema", lambda schema: None)
    monkeypatch.setattr(
        module.pd,
        "read_parquet",
        lambda *args, **kwargs: pd.DataFrame(),
    )
    monkeypatch.setattr(
        module,
        "validate_sequence_common_origin_identity",
        lambda sequences, origins: None,
    )
    availability = FitAvailability(
        available=False,
        failure_reason="sequence_fit_rows_unavailable",
        fit_status_counts={
            "success": 8925,
            "autoregressive_target_unavailable": 488,
        },
        failure_reason_counts={"missing_target_state": 488},
    )
    monkeypatch.setattr(module, "inspect_fit_availability", lambda *args, **kwargs: availability)
    def forbidden_fit(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("unavailable P1 must not tensorize or fit")

    monkeypatch.setattr(module, "load_window_bundle", forbidden_fit)
    monkeypatch.setattr(module, "fit_available_slot", forbidden_fit)
    paths = _temporal_test_paths(tmp_path)
    authority = _p1_20260612_consumer_authority(
        builder_record=current_builder_record,
        mh_lock_record=_file_record(mh_lock),
        mh_companion_record=_file_record(mh_companion),
        mi_lock_record=_file_record(mi_lock),
        mi_companion_record=_file_record(mi_companion),
        auditor_record=_file_record(auditor),
    )
    _run_temporal_slot(
        args=Namespace(model_id="P1", base_seed=20_260_612, device="cpu"),
        paths=paths,
        p1_temporal_consumer_authority=authority,
    )

    payload = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    assert payload["slot_status"] == "model_unavailable"
    assert payload["fit_status"] == "not_attempted"
    assert payload["fit_status_counts"] == availability.fit_status_counts
    assert payload["failure_reason_counts"] == availability.failure_reason_counts
    for name, path in paths.items():
        assert _path_entry_exists(path) is (name in {"report", "manifest"})


def test_unexpected_fit_runtime_error_propagates_without_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.experiments import train_closure_pipe as module

    def boom(*args: object, **kwargs: object) -> object:
        raise RuntimeError("technical failure")

    monkeypatch.setattr(module, "fit_closure_pipe", boom)
    bundle = WindowBundle(
        metadata=pd.DataFrame(),
        x=np.empty((0, 12, 13), dtype=np.float32),
        y=np.empty((0, 9), dtype=np.float32),
    )
    manifest = tmp_path / "manifest.json"
    with pytest.raises(RuntimeError, match="technical failure"):
        fit_available_slot(bundle, model_id="P0", base_seed=1729, device="cpu")
    assert not manifest.exists()


def test_main_stops_at_external_gate_before_sequence_io(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.experiments import train_closure_pipe as module

    class GateStopped(RuntimeError):
        pass

    fake_lock = types.ModuleType(
        "src.experiments.closure_p1_temporal_consumer_seed_314159_patch"
    )

    def stop_gate(
        *,
        model_id: str,
        base_seed: int,
        device: str,
    ) -> dict[str, object]:
        assert (model_id, base_seed) == ("P1", 314_159)
        assert device == "cpu"
        raise GateStopped

    setattr(
        fake_lock,
        "require_p1_temporal_consumer_seed_314159_patch_authorized",
        stop_gate,
    )
    monkeypatch.setitem(sys.modules, fake_lock.__name__, fake_lock)
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: Namespace(model_id="P1", base_seed=314_159, device="cpu"),
    )

    def forbidden_after_gate(*args: object, **kwargs: object) -> object:
        raise AssertionError("MO gate must stop before seed, paths, guards, or slot I/O")

    monkeypatch.setattr(module, "validate_temporal_seed", forbidden_after_gate)
    monkeypatch.setattr(module, "_paths", forbidden_after_gate)
    monkeypatch.setattr(module, "_temporal_slot_guard", forbidden_after_gate)
    monkeypatch.setattr(module, "_run_temporal_slot", forbidden_after_gate)
    reads: list[object] = []
    monkeypatch.setattr(pd, "read_parquet", lambda *args, **kwargs: reads.append((args, kwargs)))

    with pytest.raises(GateStopped):
        module.main()
    assert reads == []


def test_main_orders_gate_seed_paths_guard_and_slot_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import train_closure_pipe as module

    events: list[str] = []
    fake_lock = types.ModuleType(
        "src.experiments.closure_p1_temporal_consumer_seed_314159_patch"
    )
    authority: dict[str, object] = {
        "p1_artifact_builder_record": {
            "path": "src/experiments/build_closure_pipe_sequences.py",
            "bytes": 1,
            "sha256": "1" * 64,
        },
        "current_runtime_builder_record": {
            "path": "src/experiments/build_closure_pipe_sequences.py",
            "bytes": 1,
            "sha256": "1" * 64,
        },
    }

    def gate(*, model_id: str, base_seed: int, device: str) -> dict[str, object]:
        assert (model_id, base_seed) == ("P1", 314_159)
        assert device == "cpu"
        events.append("gate")
        return authority

    setattr(
        fake_lock,
        "require_p1_temporal_consumer_seed_314159_patch_authorized",
        gate,
    )
    monkeypatch.setitem(sys.modules, fake_lock.__name__, fake_lock)
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: Namespace(model_id="P1", base_seed=314_159, device="cpu"),
    )

    def validate_seed(model_id: str, base_seed: int) -> None:
        assert (model_id, base_seed) == ("P1", 314_159)
        events.append("seed")

    monkeypatch.setattr(module, "validate_temporal_seed", validate_seed)
    relative_paths = {
        name: Path(f"slot/{name}.artifact")
        for name in (*MODEL_ARTIFACT_OUTPUT_NAMES, "manifest")
    }

    def paths(model_id: str, base_seed: int) -> dict[str, Path]:
        assert (model_id, base_seed) == ("P1", 314_159)
        events.append("paths")
        return relative_paths

    monkeypatch.setattr(module, "_paths", paths)

    @contextmanager
    def guard(model_id: str, base_seed: int) -> Any:
        assert (model_id, base_seed) == ("P1", 314_159)
        events.append("guard-enter")
        try:
            yield
        finally:
            events.append("guard-exit")

    monkeypatch.setattr(module, "_temporal_slot_guard", guard)

    def run(
        *,
        args: Namespace,
        paths: Mapping[str, Path],
        p1_temporal_consumer_authority: Mapping[str, Any],
    ) -> None:
        assert args.model_id == "P1"
        assert set(paths) == set(relative_paths)
        assert p1_temporal_consumer_authority is authority
        events.append("run")

    monkeypatch.setattr(module, "_run_temporal_slot", run)
    module.main()

    assert events == ["gate", "seed", "paths", "guard-enter", "run", "guard-exit"]
