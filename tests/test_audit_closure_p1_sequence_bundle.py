from __future__ import annotations

import ast
import hashlib
import os
from pathlib import Path
import socket
import stat
import subprocess
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.experiments import audit_closure_p1_sequence_bundle as audit
from src.experiments.build_closure_pipe_sequences import (
    INPUT_COLUMNS,
    SEQUENCE_COLUMNS,
    SEQUENCE_VERSION,
    SURFACE_ID,
    TARGET_COLUMNS,
    SequenceBuildAudit,
    sequence_arrow_table,
)


EXPECTED_BASE_SEED = 1729


def _sample_frame() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for index, success in enumerate((True, False)):
        origin: Any = cast(Any, pd.Period("2018-01", freq="M")) + index
        row: dict[str, object] = {
            "sequence_version": SEQUENCE_VERSION,
            "surface_id": SURFACE_ID,
            "model_id": "P1",
            "base_seed": EXPECTED_BASE_SEED,
            "source_id": "wqp",
            "site_id": f"site-{index}",
            "common_origin_id": f"origin-{index}",
            "evaluation_unit_id": f"unit-{index}",
            "holdout_group_id": f"wqp::site-{index}",
            "assignment_role": "development",
            "time_role": "training" if success else "model_selection",
            "origin_year_month": str(origin),
            "target_year_month": str(origin + 1),
            "history_start_year_month": str(origin - 11),
            "history_end_year_month": str(origin),
            "history_length_months": 12,
            "sequence_status": (
                "success" if success else "autoregressive_target_unavailable"
            ),
            "failure_reason": "" if success else "missing_target_state",
        }
        row.update(
            {
                column: [float(np.float32(0.1 + index * 0.01))] * 12
                if success
                else None
                for column in INPUT_COLUMNS
            }
        )
        row.update(
            {
                column: float(np.float32(0.2 + index * 0.01))
                if success
                else None
                for column in TARGET_COLUMNS
            }
        )
        rows.append(row)
    return pd.DataFrame(rows, columns=SEQUENCE_COLUMNS)


def _replace_column(
    table: pa.Table,
    column: str,
    field: pa.Field,
    values: pa.Array,
) -> pa.Table:
    return table.set_column(table.schema.get_field_index(column), field, values)


def _replace_input(table: pa.Table, values: pa.Array) -> pa.Table:
    column = INPUT_COLUMNS[0]
    return _replace_column(
        table,
        column,
        pa.field(column, pa.list_(pa.float32(), 12), nullable=True),
        values,
    )


def _two_row_payload(
    monkeypatch: pytest.MonkeyPatch,
    frame: pd.DataFrame | None = None,
) -> pa.Table:
    monkeypatch.setattr(audit, "EXPECTED_INTENT_ORIGINS", 2)
    monkeypatch.setattr(
        audit,
        "EXPECTED_STATUS_COUNTS",
        {"success": 1, "autoregressive_target_unavailable": 1},
    )
    monkeypatch.setattr(
        audit,
        "EXPECTED_ROLE_COUNTS",
        {"training": 1, "model_selection": 1},
    )
    return sequence_arrow_table(_sample_frame() if frame is None else frame)


def test_physical_payload_accepts_exact_p1_seed_and_failure_null_encoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = audit._validate_physical_payload(_two_row_payload(monkeypatch))

    assert evidence == {
        "rows": 2,
        "successful_rows": 1,
        "failed_rows": 1,
        "failed_input_tensors_all_null": len(INPUT_COLUMNS),
        "failed_targets_null": len(TARGET_COLUMNS),
    }


@pytest.mark.parametrize(
    "seeds",
    (
        [None, None],
        [EXPECTED_BASE_SEED, None],
        [EXPECTED_BASE_SEED, 20260612],
    ),
    ids=("all-null", "partially-null", "cross-seed"),
)
def test_physical_payload_rejects_nonexact_seed_values(
    seeds: list[int | None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = _two_row_payload(monkeypatch)
    table = _replace_column(
        table,
        "base_seed",
        pa.field("base_seed", pa.int64(), nullable=True),
        pa.array(seeds, type=pa.int64()),
    )

    with pytest.raises(audit.ClosureP1SequenceAuditError, match="base_seed"):
        audit._validate_physical_payload(table)


def test_physical_payload_rejects_seed_type_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = _two_row_payload(monkeypatch)
    table = _replace_column(
        table,
        "base_seed",
        pa.field("base_seed", pa.string(), nullable=False),
        pa.array([str(EXPECTED_BASE_SEED)] * 2, type=pa.string()),
    )

    with pytest.raises(audit.ClosureP1SequenceAuditError, match="base_seed"):
        audit._validate_physical_payload(table)


@pytest.mark.parametrize("mutation", ("extra", "reordered", "metadata-type"))
def test_physical_payload_rejects_schema_or_column_order_drift(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = _two_row_payload(monkeypatch)
    if mutation == "extra":
        table = table.append_column("forbidden_extra", pa.array([1, 2], type=pa.int64()))
    elif mutation == "reordered":
        names = list(table.schema.names)
        names[0], names[1] = names[1], names[0]
        table = table.select(names)
    else:
        table = _replace_column(
            table,
            "history_length_months",
            pa.field("history_length_months", pa.int64(), nullable=False),
            pa.array([12, 12], type=pa.int64()),
        )

    with pytest.raises(
        audit.ClosureP1SequenceAuditError,
        match="columns/order|physical schema",
    ):
        audit._validate_physical_payload(table)


@pytest.mark.parametrize("mutation", ("variable-list", "wrong-size", "float64"))
def test_physical_payload_rejects_input_physical_type_drift(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = _two_row_payload(monkeypatch)
    column = INPUT_COLUMNS[0]
    if mutation == "variable-list":
        value_type = pa.list_(pa.float32())
        rows = [[float(np.float32(0.1))] * 12, [None] * 12]
    elif mutation == "wrong-size":
        value_type = pa.list_(pa.float32(), 11)
        rows = [[float(np.float32(0.1))] * 11, [None] * 11]
    else:
        value_type = pa.list_(pa.float64(), 12)
        rows = [[0.1] * 12, [None] * 12]
    table = _replace_column(
        table,
        column,
        pa.field(column, value_type, nullable=True),
        pa.array(rows, type=value_type),
    )

    with pytest.raises(audit.ClosureP1SequenceAuditError, match="schema"):
        audit._validate_physical_payload(table)


@pytest.mark.parametrize("mutation", ("parent-null", "partial-null", "nonfinite-success"))
def test_physical_payload_rejects_invalid_input_null_or_numeric_encoding(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = _two_row_payload(monkeypatch)
    if mutation == "parent-null":
        rows: list[list[float | None] | None] = [
            [float(np.float32(0.1))] * 12,
            None,
        ]
    elif mutation == "partial-null":
        rows = [
            [float(np.float32(0.1))] * 12,
            [None] * 11 + [float(np.float32(0.0))],
        ]
    else:
        rows = [
            [float(np.float32(0.1))] * 11 + [float("inf")],
            [None] * 12,
        ]
    values = pa.array(rows, type=pa.list_(pa.float32(), 12))

    with pytest.raises(
        audit.ClosureP1SequenceAuditError,
        match="physically valid|all-null tensor|non-finite",
    ):
        audit._validate_physical_payload(_replace_input(table, values))


@pytest.mark.parametrize("mutation", ("failure-present", "success-nonfinite"))
def test_physical_payload_rejects_invalid_target_null_or_numeric_encoding(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = _two_row_payload(monkeypatch)
    column = TARGET_COLUMNS[0]
    values = (
        [float(np.float32(0.2)), float(np.float32(0.3))]
        if mutation == "failure-present"
        else [float("nan"), None]
    )
    table = _replace_column(
        table,
        column,
        pa.field(column, pa.float32(), nullable=True),
        pa.array(values, type=pa.float32()),
    )

    with pytest.raises(
        audit.ClosureP1SequenceAuditError,
        match="target null policy|non-finite",
    ):
        audit._validate_physical_payload(table)


def _closed_namespace_snapshot(*, pointer_present: bool = False) -> dict[str, Any]:
    data = [audit.P1_SEQUENCE_PATH.name]
    if pointer_present:
        data.append(audit.P1_POINTER_PATH.name)
    return {
        "data": sorted(data),
        "reports": sorted(
            (audit.P1_MANIFEST_PATH.name, audit.P1_SUMMARY_PATH.name)
        ),
        "sequence_guards": None,
        "model_files": None,
        "model_reports": None,
        "consumer_guards": None,
        "protocol": [],
    }


def test_namespace_accepts_exact_pre_or_post_dvc_slot_state() -> None:
    pre_dvc = audit._validate_closed_namespace(_closed_namespace_snapshot())
    post_dvc = audit._validate_closed_namespace(
        _closed_namespace_snapshot(pointer_present=True)
    )

    assert pre_dvc["pointer_present"] is False
    assert post_dvc["pointer_present"] is True
    for evidence in (pre_dvc, post_dvc):
        integrity = evidence["slot_integrity"]
        assert integrity["required_sequence_outputs_present"] is True
        assert integrity["sequence_temporary_or_guard_paths_present"] == []
        assert integrity["registered_slot_path_count"] == len(audit.P1_SLOT_PATHS)
        assert integrity["registered_slot_paths_sha256"] == audit._path_digest(
            audit.P1_SLOT_PATHS
        )
        assert (
            integrity["registered_slot_present_count"]
            + integrity["registered_slot_absent_count"]
            == len(audit.P1_SLOT_PATHS)
        )
        assert len(integrity["registered_slot_present_paths"]) == integrity[
            "registered_slot_present_count"
        ]
        assert len(integrity["registered_slot_absent_paths"]) == integrity[
            "registered_slot_absent_count"
        ]
        progression = evidence["progression_observation"]
        assert progression["consumer_seed_1729_present_paths"] == []
        assert progression["future_seed_present_paths"] == []
        assert progression["e0_m_present_paths"] == []
        assert progression["outcome_access_log_present"] is False
        assert progression["pre_consumer_and_pre_e0_m_clear_now"] is True


@pytest.mark.parametrize(
    ("namespace", "forbidden_name"),
    (
        ("data", f"{audit.P1_SEQUENCE_PATH.name}.tmp"),
        ("data", f"{audit.P1_POINTER_PATH.name}.tmp"),
        ("reports", f"{audit.P1_SUMMARY_PATH.name}.tmp"),
        ("reports", f"{audit.P1_MANIFEST_PATH.name}.tmp"),
        ("sequence_guards", f"P1_seed_{EXPECTED_BASE_SEED}.guard"),
    ),
)
def test_namespace_rejects_seed_1729_temporary_or_guard_state(
    namespace: str,
    forbidden_name: str,
) -> None:
    snapshot = _closed_namespace_snapshot()
    current = snapshot[namespace]
    snapshot[namespace] = [forbidden_name] if current is None else [*current, forbidden_name]

    with pytest.raises(
        audit.ClosureP1SequenceAuditError,
        match="temporary or guard state",
    ):
        audit._validate_closed_namespace(snapshot)


def test_namespace_requires_the_exact_seven_key_snapshot_dialect() -> None:
    snapshot = _closed_namespace_snapshot()
    del snapshot["consumer_guards"]

    with pytest.raises(
        audit.ClosureP1SequenceAuditError,
        match="snapshot dialect",
    ):
        audit._validate_closed_namespace(snapshot)


@pytest.mark.parametrize(
    ("namespace", "name"),
    (
        ("data", "seed_999.parquet"),
        ("model_reports", "unregistered.json"),
        ("sequence_guards", "P1_seed_999.guard"),
    ),
)
def test_namespace_rejects_unregistered_p1_entries(
    namespace: str,
    name: str,
) -> None:
    snapshot = _closed_namespace_snapshot()
    current = snapshot[namespace]
    snapshot[namespace] = [name] if current is None else [*current, name]

    with pytest.raises(audit.ClosureP1SequenceAuditError, match="Unregistered"):
        audit._validate_closed_namespace(snapshot)


def test_namespace_observes_future_e0_m_and_outcome_without_authorizing_them() -> None:
    snapshot = _closed_namespace_snapshot()
    future_sequence = audit._registered_seed_paths(20260612)[0]
    consumer_path = audit.P1_CONSUMER_PATHS[0]
    e0_m_path = audit.E0_M_OUTPUT_PATHS[0]
    snapshot["data"] = [*snapshot["data"], future_sequence.name]
    snapshot["model_files"] = [consumer_path.name]
    snapshot["protocol"] = [e0_m_path.name, audit.OUTCOME_ACCESS_LOG_PATH.name]

    evidence = audit._validate_closed_namespace(snapshot)
    progression = evidence["progression_observation"]

    assert progression["scope"] == "presence_only_no_authorization_or_content_inference"
    assert progression["consumer_seed_1729_present_paths"] == [consumer_path.as_posix()]
    assert progression["future_seed_present_paths"] == [future_sequence.as_posix()]
    assert progression["e0_m_present_paths"] == [e0_m_path.as_posix()]
    assert progression["outcome_access_log_present"] is True
    assert progression["pre_consumer_and_pre_e0_m_clear_now"] is False

    with pytest.raises(
        audit.ClosureP1SequenceAuditError,
        match="pre-consumer CLI gate",
    ):
        audit._require_pre_consumer_progression_clear(evidence)


def test_pre_consumer_cli_gate_accepts_the_current_clear_observation() -> None:
    evidence = audit._validate_closed_namespace(_closed_namespace_snapshot())

    audit._require_pre_consumer_progression_clear(evidence)


def _strict_physical_json(path: Path) -> dict[str, Any]:
    return audit._decode_strict_json(
        (audit.PROJECT_ROOT / path).read_bytes(),
        path=path.as_posix(),
    )


def _expected_input_record(path: Path) -> dict[str, Any]:
    matches = [
        dict(record)
        for record in audit.EXPECTED_INPUT_RECORDS
        if record["path"] == path.as_posix()
    ]
    assert len(matches) == 1
    return matches[0]


def test_state_manifest_accepts_exact_seed_1729_and_binds_state() -> None:
    payload = _strict_physical_json(audit.P1_STATE_MANIFEST_PATH)

    audit._validate_state_manifest(
        payload,
        state_record=_expected_input_record(audit.P1_STATE_PATH),
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("model_id", "P0"),
        ("base_seed", 20260612),
        ("slot_status", "failed"),
        ("future_outcomes_accessed", True),
    ),
)
def test_state_manifest_rejects_identity_or_authorization_drift(
    field: str,
    value: object,
) -> None:
    payload = _strict_physical_json(audit.P1_STATE_MANIFEST_PATH)
    payload[field] = value

    with pytest.raises(
        audit.ClosureP1SequenceAuditError,
        match="state manifest field",
    ):
        audit._validate_state_manifest(
            payload,
            state_record=_expected_input_record(audit.P1_STATE_PATH),
        )


def test_state_manifest_rejects_physical_state_binding_drift() -> None:
    payload = _strict_physical_json(audit.P1_STATE_MANIFEST_PATH)
    outputs = cast(list[dict[str, Any]], payload["outputs"])
    state_output = next(
        record
        for record in outputs
        if record.get("path") == audit.P1_STATE_PATH.as_posix()
    )
    state_output["sha256"] = "0" * 64

    with pytest.raises(
        audit.ClosureP1SequenceAuditError,
        match="does not bind the physical adaptive state",
    ):
        audit._validate_state_manifest(
            payload,
            state_record=_expected_input_record(audit.P1_STATE_PATH),
        )


def _e0_mc_physical_records() -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for record in (
        *audit.EXPECTED_E0_MC_INPUT_RECORDS,
        *audit.EXPECTED_E0_MC_PATCH_RECORDS,
    ):
        records[str(record["path"])] = audit._physical_record(record)
    return records


def _validate_physical_e0_mc(
    lock: dict[str, Any],
    companion: dict[str, Any],
    *,
    physical_records: dict[str, dict[str, Any]] | None = None,
    state_manifest_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return audit._validate_e0_mc_reference(
        lock,
        companion,
        lock_record=_expected_input_record(audit.E0_MC_LOCK_PATH),
        physical_records=(
            _e0_mc_physical_records()
            if physical_records is None
            else physical_records
        ),
        state_manifest_record=(
            _expected_input_record(audit.P1_STATE_MANIFEST_PATH)
            if state_manifest_record is None
            else state_manifest_record
        ),
    )


def test_e0_mc_reference_accepts_exact_physical_post_consumption_authority() -> None:
    evidence = _validate_physical_e0_mc(
        _strict_physical_json(audit.E0_MC_LOCK_PATH),
        _strict_physical_json(audit.E0_MC_COMPANION_PATH),
    )

    assert evidence["physical_input_count"] == len(audit.EXPECTED_E0_MC_INPUT_RECORDS)
    assert evidence["physical_patch_component_count"] == len(
        audit.EXPECTED_E0_MC_PATCH_RECORDS
    )
    assert evidence["state_manifest_physically_reconciled"] is True
    assert evidence["base_authorities_physically_reconciled"] is True
    assert evidence["effective_loader_called_by_auditor"] is False
    assert evidence["one_shot_reconsumed_by_auditor"] is False


@pytest.mark.parametrize(
    "mutation",
    ("authorization", "physical-input", "state-manifest", "companion-output"),
)
def test_e0_mc_reference_rejects_authority_or_physical_binding_drift(
    mutation: str,
) -> None:
    lock = _strict_physical_json(audit.E0_MC_LOCK_PATH)
    companion = _strict_physical_json(audit.E0_MC_COMPANION_PATH)
    physical_records = _e0_mc_physical_records()
    state_manifest_record = _expected_input_record(audit.P1_STATE_MANIFEST_PATH)
    if mutation == "authorization":
        cast(dict[str, Any], lock["authorizations"])["p1_fit_authorized"] = True
    elif mutation == "physical-input":
        builder_path = "src/experiments/build_closure_pipe_sequences.py"
        physical_records[builder_path]["sha256"] = "0" * 64
    elif mutation == "state-manifest":
        state_manifest_record["sha256"] = "0" * 64
    else:
        outputs = cast(list[dict[str, Any]], companion["outputs"])
        outputs[0]["sha256"] = "0" * 64

    with pytest.raises(audit.ClosureP1SequenceAuditError, match="E0-MC"):
        _validate_physical_e0_mc(
            lock,
            companion,
            physical_records=physical_records,
            state_manifest_record=state_manifest_record,
        )


def _closed_build_audit() -> SequenceBuildAudit:
    return SequenceBuildAudit(
        intent_origins=9_732,
        successful_origins=9_227,
        failed_origins=505,
        role_counts=dict(audit.EXPECTED_ROLE_COUNTS),
        status_counts=dict(audit.EXPECTED_STATUS_COUNTS),
        failure_reason_counts=dict(audit.EXPECTED_FAILURE_REASON_COUNTS),
        delta_previous_month_missing_history_values=496,
        delta_previous_month_missing_target_values=0,
    )


def _validate_physical_sequence_manifest(payload: dict[str, Any]) -> None:
    audit._validate_manifest(
        payload,
        builder_record=_expected_input_record(
            Path("src/experiments/build_closure_pipe_sequences.py")
        ),
        input_records=[dict(record) for record in audit.EXPECTED_INPUT_RECORDS],
        output_records=[
            dict(audit.EXPECTED_BUNDLE_RECORDS[path.as_posix()])
            for path in (audit.P1_SEQUENCE_PATH, audit.P1_SUMMARY_PATH)
        ],
        audit=_closed_build_audit(),
        boundary={"holdout_overlap": 0, "post_2021_rows": 0},
    )


def test_sequence_manifest_accepts_exact_sections_and_closed_counts() -> None:
    _validate_physical_sequence_manifest(
        _strict_physical_json(audit.P1_MANIFEST_PATH)
    )


@pytest.mark.parametrize(
    "mutation",
    ("identity", "mapping", "inputs", "output", "counts", "dialect"),
)
def test_sequence_manifest_rejects_identity_section_count_or_dialect_drift(
    mutation: str,
) -> None:
    payload = _strict_physical_json(audit.P1_MANIFEST_PATH)
    if mutation == "identity":
        payload["future_outcomes_accessed"] = True
    elif mutation == "mapping":
        cast(dict[str, Any], payload["input_state_mapping"])["yN"] = "yN"
    elif mutation == "inputs":
        payload["inputs"] = list(reversed(cast(list[Any], payload["inputs"])))
    elif mutation == "output":
        cast(list[dict[str, Any]], payload["outputs"])[0]["sha256"] = "0" * 64
    elif mutation == "counts":
        cast(dict[str, Any], payload["counts"])["intent_origins"] = 9_733
    else:
        payload["unexpected"] = True

    with pytest.raises(audit.ClosureP1SequenceAuditError, match="manifest"):
        _validate_physical_sequence_manifest(payload)


def test_sequence_manifest_strict_decoder_rejects_duplicate_keys() -> None:
    with pytest.raises(audit.ClosureP1SequenceAuditError, match="duplicate key"):
        audit._decode_strict_json(
            b'{"status":"completed","status":"drifted"}\n',
            path=audit.P1_MANIFEST_PATH.as_posix(),
        )


def _closed_boundary_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    development_rows = [
        {
            "source_id": "wqp",
            "site_id": f"development-{index:03d}",
            "assignment_role": "development",
            "holdout_group_id": f"wqp::development-{index:03d}",
        }
        for index in range(353)
    ]
    holdout_rows = [
        {
            "source_id": "wqp",
            "site_id": f"holdout-{index:03d}",
            "assignment_role": "internal_holdout",
            "holdout_group_id": f"wqp::holdout-{index:03d}",
        }
        for index in range(88)
    ]
    assignment = pd.DataFrame([*development_rows, *holdout_rows])
    sequence = pd.DataFrame(
        [
            {**row, "target_year_month": "2021-12"}
            for row in development_rows
        ]
    )
    return sequence, assignment


def test_boundary_accepts_exact_development_holdout_and_cutoff_geometry() -> None:
    sequence, assignment = _closed_boundary_frames()

    evidence = audit._derive_boundary_evidence(sequence, assignment)

    assert evidence == {
        "development_assignment_locations": 353,
        "holdout_assignment_locations": 88,
        "sequence_locations": 353,
        "holdout_overlap": 0,
        "holdout_overlap_rows": 0,
        "unknown_assignment_locations": 0,
        "assignment_role_mismatch_rows": 0,
        "holdout_group_mismatch_rows": 0,
        "post_2021_rows": 0,
    }


@pytest.mark.parametrize(
    "mutation",
    ("holdout", "unknown", "post-2021", "assignment-role", "holdout-group", "source"),
)
def test_boundary_rejects_holdout_unknown_post_cutoff_or_assignment_drift(
    mutation: str,
) -> None:
    sequence, assignment = _closed_boundary_frames()
    if mutation == "holdout":
        sequence.loc[0, ["site_id", "assignment_role", "holdout_group_id"]] = [
            "holdout-000",
            "internal_holdout",
            "wqp::holdout-000",
        ]
    elif mutation == "unknown":
        sequence.loc[0, ["site_id", "holdout_group_id"]] = [
            "unknown",
            "wqp::unknown",
        ]
    elif mutation == "post-2021":
        sequence.loc[0, "target_year_month"] = "2022-01"
    elif mutation == "assignment-role":
        sequence.loc[0, "assignment_role"] = "internal_holdout"
    elif mutation == "holdout-group":
        sequence.loc[0, "holdout_group_id"] = "wqp::drifted"
    else:
        sequence.loc[0, "source_id"] = "nla"

    with pytest.raises(audit.ClosureP1SequenceAuditError):
        audit._derive_boundary_evidence(sequence, assignment)


def _fit_evidence_frame() -> pd.DataFrame:
    roles = ["training"] * 8_352 + ["model_selection"] * 1_061 + [
        "calibration_threshold"
    ] * 319
    statuses = ["success"] * len(roles)
    reasons = [""] * len(roles)
    for start, failures in ((0, 443), (8_352, 45), (9_413, 17)):
        for index in range(start, start + failures):
            statuses[index] = "autoregressive_target_unavailable"
            reasons[index] = "missing_target_state"
    return pd.DataFrame(
        {"time_role": roles, "sequence_status": statuses, "failure_reason": reasons}
    )


def test_fit_evidence_preserves_exact_total_fit_and_calibration_denominators() -> None:
    evidence = audit._fit_evidence(_fit_evidence_frame())

    assert evidence["observed_total_status_counts"] == audit.EXPECTED_STATUS_COUNTS
    assert evidence["observed_fit_status_counts"] == audit.EXPECTED_FIT_STATUS_COUNTS
    assert evidence["observed_calibration_failure_count"] == 17
    assert evidence["expected_fit_status"] == "not_attempted"
    assert evidence["expected_temporal_slot_status"] == "model_unavailable"
    assert evidence["expected_failure_reason"] == "sequence_fit_rows_unavailable"
    assert evidence["consumer_executed_by_auditor"] is False
    assert evidence["fit_or_model_construction_executed_by_auditor"] is False


@pytest.mark.parametrize("mutation", ("total", "fit", "calibration"))
def test_fit_evidence_rejects_denominator_or_role_allocation_drift(
    mutation: str,
) -> None:
    frame = _fit_evidence_frame()
    if mutation == "total":
        frame.loc[0, ["sequence_status", "failure_reason"]] = ["success", ""]
    elif mutation == "fit":
        frame.loc[0, ["sequence_status", "failure_reason"]] = ["success", ""]
        frame.loc[9_430, ["sequence_status", "failure_reason"]] = [
            "autoregressive_target_unavailable",
            "missing_target_state",
        ]
    else:
        frame.loc[9_413, "time_role"] = "unexpected_role"

    with pytest.raises(audit.ClosureP1SequenceAuditError):
        audit._fit_evidence(frame)


def test_summary_bytes_preserve_exact_closed_order_and_counts() -> None:
    expected = (
        "time_role,sequence_status,failure_reason,rows\n"
        "calibration_threshold,autoregressive_target_unavailable,missing_target_state,17\n"
        "calibration_threshold,success,,302\n"
        "model_selection,autoregressive_target_unavailable,missing_target_state,45\n"
        "model_selection,success,,1016\n"
        "training,autoregressive_target_unavailable,missing_target_state,443\n"
        "training,success,,7909\n"
    ).encode("utf-8")

    assert audit._summary_bytes(_fit_evidence_frame()) == expected
    assert (audit.PROJECT_ROOT / audit.P1_SUMMARY_PATH).read_bytes() == expected


def _pinned(path: Path, payload: bytes) -> SimpleNamespace:
    return SimpleNamespace(
        payload=payload,
        relative_path=path,
        record={
            "path": path.as_posix(),
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        },
    )


def test_explicit_dvc_pointer_binds_exact_p1_payload() -> None:
    payload = b"closed-p1-seed-1729-payload"
    digest = hashlib.md5(payload, usedforsecurity=False).hexdigest()
    pointer_payload = (
        "outs:\n"
        f"- md5: {digest}\n"
        f"  size: {len(payload)}\n"
        "  hash: md5\n"
        f"  path: {audit.P1_SEQUENCE_PATH.name}\n"
    ).encode("utf-8")

    evidence = audit._validate_dvc_pointer(
        _pinned(audit.P1_SEQUENCE_PATH, payload),
        _pinned(audit.P1_POINTER_PATH, pointer_payload),
    )

    assert evidence["state"] == "post_dvc"
    assert evidence["pointer_payload_binding_verified"] is True
    assert evidence["cache_verified"] is False
    assert evidence["remote_verified"] is False
    assert evidence["dvc_command_executed_by_auditor"] is False


@pytest.mark.parametrize("mutation", ("size", "digest", "path"))
def test_explicit_dvc_pointer_rejects_payload_or_slot_drift(mutation: str) -> None:
    payload = b"closed-p1-seed-1729-payload"
    digest = hashlib.md5(payload, usedforsecurity=False).hexdigest()
    size = len(payload)
    name = audit.P1_SEQUENCE_PATH.name
    if mutation == "size":
        size += 1
    elif mutation == "digest":
        digest = "0" * 32
    else:
        name = "seed_20260612.parquet"
    pointer_payload = (
        "outs:\n"
        f"- md5: {digest}\n"
        f"  size: {size}\n"
        "  hash: md5\n"
        f"  path: {name}\n"
    ).encode("utf-8")

    with pytest.raises(audit.ClosureP1SequenceAuditError, match="pointer"):
        audit._validate_dvc_pointer(
            _pinned(audit.P1_SEQUENCE_PATH, payload),
            _pinned(audit.P1_POINTER_PATH, pointer_payload),
        )


def test_pinned_reader_rejects_symlink_ancestor_and_fifo(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    (real / "payload.bin").write_bytes(b"payload")
    (tmp_path / "linked").symlink_to(real, target_is_directory=True)
    fifo = tmp_path / "payload.fifo"
    os.mkfifo(fifo)

    with audit.secure_reads._RepoReadSession(tmp_path) as session:
        with pytest.raises(
            audit.secure_reads.ClosureP0SequenceAuditError,
            match="ancestor",
        ):
            session.pin(tmp_path / "linked" / "payload.bin")
        with pytest.raises(
            audit.secure_reads.ClosureP0SequenceAuditError,
            match="regular file",
        ):
            session.pin(fifo)


def test_pinned_reader_detects_mutate_then_restore(tmp_path: Path) -> None:
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"original")
    original_mtime = payload.stat().st_mtime_ns

    with pytest.raises(
        audit.secure_reads.ClosureP0SequenceAuditError,
        match="Pinned audit file changed",
    ):
        with audit.secure_reads._RepoReadSession(tmp_path) as session:
            session.pin(payload)
            payload.write_bytes(b"modified")
            payload.write_bytes(b"original")
            os.utime(payload, ns=(payload.stat().st_atime_ns, original_mtime))


def test_auditor_source_has_no_mutator_process_network_or_trainer() -> None:
    source = Path(audit.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_calls = {
        ".mkdir(",
        ".rmdir(",
        ".touch(",
        ".unlink(",
        ".write_bytes(",
        ".write_text(",
        "os.link(",
        "os.mkdir(",
        "os.remove(",
        "os.rename(",
        "os.replace(",
        "os.unlink(",
        "subprocess.",
        "socket.",
        "requests.",
        "urllib.",
    }

    assert isinstance(tree, ast.Module)
    assert not {call for call in forbidden_calls if call in source}
    assert "train_closure_pipe" not in source
    assert "write_sequence_parquet" not in source
    assert "pq.write_table" not in source
    assert "require_p1_sequence_historical_anfis_authorized" not in source


def test_cli_is_closed_and_requires_check_only() -> None:
    assert audit.parse_args(["--check-only"]).check_only is True
    with pytest.raises(SystemExit):
        audit.parse_args([])
    with pytest.raises(SystemExit):
        audit.parse_args(["--check-only", "--output", "unexpected.json"])


def _lexical_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _fingerprint(path: Path) -> tuple[int, int, int, int, int, int, int]:
    metadata = path.lstat()
    return (
        metadata.st_dev,
        metadata.st_ino,
        stat.S_IFMT(metadata.st_mode),
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _real_audit_snapshot() -> dict[str, Any]:
    paths = [
        audit.PROJECT_ROOT / audit.P1_SEQUENCE_PATH,
        audit.PROJECT_ROOT / audit.P1_SUMMARY_PATH,
        audit.PROJECT_ROOT / audit.P1_MANIFEST_PATH,
        audit.PROJECT_ROOT / audit.P1_POINTER_PATH,
    ]
    files: dict[str, Any] = {}
    for path in paths:
        if not _lexical_exists(path):
            continue
        files[path.relative_to(audit.PROJECT_ROOT).as_posix()] = {
            "fingerprint": _fingerprint(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    directories: dict[str, Any] = {}
    for relative in audit.NAMESPACE_DIRECTORIES.values():
        path = audit.PROJECT_ROOT / relative
        key = path.relative_to(audit.PROJECT_ROOT).as_posix()
        if not _lexical_exists(path):
            directories[key] = None
            continue
        directories[key] = {
            "fingerprint": _fingerprint(path),
            "entries": sorted(entry.name for entry in path.iterdir()),
        }
    git_status = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=audit.PROJECT_ROOT,
        check=True,
        capture_output=True,
    ).stdout
    return {"files": files, "directories": directories, "git_status": git_status}


@pytest.mark.skipif(
    not (audit.PROJECT_ROOT / audit.P1_SEQUENCE_PATH).is_file(),
    reason="The ignored P1/1729 payload exists only in an authorized data workspace",
)
def test_real_p1_seed_1729_audit_pass_is_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _real_audit_snapshot()
    descriptors_before = len(os.listdir("/proc/self/fd"))

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("The read-only P1 auditor attempted a mutation or external call")

    with monkeypatch.context() as guarded:
        for name in (
            "mkdir",
            "unlink",
            "rename",
            "replace",
            "touch",
            "write_bytes",
            "write_text",
        ):
            guarded.setattr(Path, name, forbidden)
        for name in ("link", "mkdir", "remove", "rename", "replace", "rmdir", "unlink"):
            guarded.setattr(os, name, forbidden)
        guarded.setattr(subprocess, "run", forbidden)
        guarded.setattr(socket, "socket", forbidden)
        guarded.setattr(socket, "create_connection", forbidden)
        guarded.setattr(pq, "write_table", forbidden)
        result = audit.audit_p1_sequence_bundle()

    assert len(os.listdir("/proc/self/fd")) == descriptors_before
    assert _real_audit_snapshot() == before
    assert result["status"] == "validated"
    assert result["model_id"] == "P1"
    assert result["base_seed"] == EXPECTED_BASE_SEED
    assert result["counts"]["intent_origins"] == 9_732
    assert result["counts"]["successful_origins"] == 9_227
    assert result["counts"]["failed_origins"] == 505
    assert result["development_boundary"]["holdout_overlap"] == 0
    assert result["development_boundary"]["unknown_assignment_locations"] == 0
    assert result["development_boundary"]["post_2021_rows"] == 0
    assert result["physical_evidence"]["rows"] == 9_732
    assert result["pinned_read_session_verified"] is True
    assert result["builder_reconstruction_executed"] is True
    assert result["builder_cli_executed"] is False
    assert result["fit_or_model_construction_executed_by_auditor"] is False
    assert result["dvc_operation_executed_by_auditor"] is False
    assert result["bundle_future_outcomes_accessed"] is False
    assert result["future_outcomes_accessed_by_auditor"] is False


@pytest.mark.skipif(
    not (audit.PROJECT_ROOT / audit.P1_SEQUENCE_PATH).is_file(),
    reason="The ignored P1/1729 payload exists only in an authorized data workspace",
)
def test_real_p1_seed_1729_audit_failure_is_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _real_audit_snapshot()
    descriptors_before = len(os.listdir("/proc/self/fd"))
    original = audit._validate_physical_payload

    def injected_failure(table: pa.Table) -> dict[str, int]:
        original(table)
        raise audit.ClosureP1SequenceAuditError("injected late audit failure")

    monkeypatch.setattr(audit, "_validate_physical_payload", injected_failure)
    with pytest.raises(
        audit.ClosureP1SequenceAuditError,
        match="injected late audit failure",
    ):
        audit.audit_p1_sequence_bundle()

    assert len(os.listdir("/proc/self/fd")) == descriptors_before
    assert _real_audit_snapshot() == before
