from __future__ import annotations

import hashlib
import json
import sys
import types
from argparse import Namespace
from pathlib import Path
from typing import Any

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
    MODEL_ARTIFACT_OUTPUT_NAMES,
    WindowBundle,
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
            model_id="P0",
            base_seed=1729,
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

    contract = collect_sequence_input_contract(model_id="P0", base_seed=1729)
    observed = {str(record["path"]) for record in contract.records}
    assert observed == {
        *(path.as_posix() for path in fixed_paths),
        "reports/state_manifest.json",
        "data/state.parquet",
    }
    assert contract.state_artifact_required is True
    assert_sequence_input_contract_unchanged(contract)
    (tmp_path / training_module.DEFAULT_ASSIGNMENT).write_bytes(b"changed")
    with pytest.raises(ValueError, match="upstream input changed"):
        assert_sequence_input_contract_unchanged(contract)


def test_sequence_input_contract_keeps_prefit_unavailable_state_absent(
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
    state_manifest_path = tmp_path / "reports/state_manifest.json"
    state_manifest_path.parent.mkdir(parents=True, exist_ok=True)
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
        lambda *args, **kwargs: (False, "anfis_model_slot_unavailable", False),
    )

    contract = collect_sequence_input_contract(model_id="P1", base_seed=1729)
    assert contract.state_artifact_required is False
    assert "data/state.parquet" not in {str(record["path"]) for record in contract.records}
    state_path = tmp_path / "data/state.parquet"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_bytes(b"appeared")
    with pytest.raises(ValueError, match="state appeared"):
        assert_sequence_input_contract_unchanged(contract)


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
        "src.experiments.closure_development_runtime_sequence_patch"
    )

    def stop_gate(*, device: str | None = None, **_: object) -> dict[str, object]:
        assert device == "cpu"
        raise GateStopped

    setattr(fake_lock, "require_development_fit_authorized_with_sequence_patch", stop_gate)
    monkeypatch.setitem(sys.modules, fake_lock.__name__, fake_lock)
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: Namespace(model_id="P0", base_seed=1729, device="cpu"),
    )
    reads: list[object] = []
    monkeypatch.setattr(pd, "read_parquet", lambda *args, **kwargs: reads.append((args, kwargs)))

    with pytest.raises(GateStopped):
        module.main()
    assert reads == []
