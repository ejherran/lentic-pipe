from __future__ import annotations

import copy
import sys
import types
from argparse import Namespace
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
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
)
from src.experiments.closure_contract import load_yaml_mapping
from src.experiments.rollout_closure_pipe import (
    EXPECTED_PREDRAW_GOLDEN,
    ROLLOUT_COLUMNS,
    SAMPLE_COLUMNS,
    _load_model,
    assert_rollout_outputs_absent,
    build_closure_rollouts,
    origin_rng_records_sha256,
    rollout_arrow_table,
    rollout_origin_batch,
    rollout_origin_samples,
    validate_rollout_runtime_contract,
    validate_temporal_model_manifest,
    write_rollout_parquet,
)
from src.experiments.closure_runtime_contract import (
    rollout_predraw_sha256,
    rollout_standard_normal_predraw,
)
from src.experiments.train_closure_pipe import (
    FitAvailability,
    MODEL_ARTIFACT_OUTPUT_NAMES,
    fixed_profile,
)


def _sequence(*, status: str = "success", reason: str = "") -> pd.DataFrame:
    row: dict[str, object] = {
        "sequence_version": SEQUENCE_VERSION,
        "surface_id": SURFACE_ID,
        "model_id": "P0",
        "base_seed": None,
        "source_id": "wqp",
        "site_id": "site-A",
        "common_origin_id": "origin-A",
        "evaluation_unit_id": "unit-A-h1",
        "holdout_group_id": "wqp::site-A",
        "assignment_role": "development",
        "time_role": "model_selection",
        "origin_year_month": "2020-09",
        "target_year_month": "2020-10",
        "history_start_year_month": "2019-10",
        "history_end_year_month": "2020-09",
        "history_length_months": 12,
        "sequence_status": status,
        "failure_reason": reason,
    }
    state_values = {
        "x_yN": 0.6,
        "x_yF": 0.4,
        "x_yT": 0.7,
        "x_sigma_N": 0.1,
        "x_sigma_F": 0.1,
        "x_sigma_T": 0.1,
        "x_delta_yN": -0.2,
        "x_delta_yF": 0.1,
        "x_delta_yT": -0.3,
        "season_sin_annual": 0.0,
        "season_cos_annual": 1.0,
        "season_sin_semiannual": 0.0,
        "season_cos_semiannual": 1.0,
    }
    for column in INPUT_COLUMNS:
        row[column] = (
            None
            if status != "success"
            else np.full(12, state_values[column], dtype=np.float32)
        )
    for column in TARGET_COLUMNS:
        row[column] = np.float32(np.nan if status != "success" else 0.5)
    return pd.DataFrame([row], columns=SEQUENCE_COLUMNS)


def _common() -> pd.DataFrame:
    rows = []
    for horizon, target, available in (
        (1, "2020-10", True),
        (2, "2020-11", False),
        (3, "2020-12", True),
    ):
        rows.append(
            {
                "surface_id": SURFACE_ID,
                "source_id": "wqp",
                "site_id": "site-A",
                "common_origin_id": "origin-A",
                "evaluation_unit_id": f"unit-A-h{horizon}",
                "holdout_group_id": "wqp::site-A",
                "assignment_role": "development",
                "time_role": "model_selection",
                "origin_year_month": "2020-09",
                "target_year_month": target,
                "horizon_months": horizon,
                "history_start_year_month": "2019-10",
                "history_end_year_month": "2020-09",
                "history_length_months": 12,
                "target_evaluable": available,
            }
        )
    return pd.DataFrame(rows)


def _model() -> object:
    torch = pytest.importorskip("torch")

    class PersistenceModel(torch.nn.Module):
        def forward(self, x: Any) -> tuple[Any, Any]:
            mu = x[:, -1, :9]
            logvar = torch.full_like(mu, -10.0)
            return mu, logvar

    return PersistenceModel()


def _window() -> np.ndarray:
    row = _sequence().iloc[0]
    return np.column_stack([np.asarray(row[column], dtype=np.float32) for column in INPUT_COLUMNS]).astype(
        np.float32
    )


def test_origin_rollout_uses_pcg64_golden_and_preserves_signed_deltas() -> None:
    torch = pytest.importorskip("torch")
    result = rollout_origin_samples(
        _model(),
        _window(),
        blend_weights=[1.0] * 9,
        base_seed=1729,
        source_id="wqp",
        site_id="site-A",
        origin_year_month="2020-09",
        device=torch.device("cpu"),
    )

    assert result.state_samples.shape == (3, 128, 9)
    assert result.state_samples.dtype == np.float32
    assert result.irc_samples.shape == (3, 128)
    assert result.irc_samples.dtype == np.float64
    assert np.all(result.state_samples[:, :, :6] >= 0.0)
    assert np.all(result.state_samples[:, :, :6] <= 1.0)
    assert np.any(result.state_samples[:, :, 6:] < 0.0)
    assert np.all(result.state_samples[:, :, 6:] >= -1.0)
    assert np.all(result.state_samples[:, :, 6:] <= 1.0)
    assert np.allclose(result.raw_bloom_scores, result.irc_samples.mean(axis=1))

    golden = rollout_predraw_sha256(
        rollout_standard_normal_predraw(
            1729,
            source_id="wqp",
            site_id="A",
            origin_year_month="2020-01",
        )
    )
    assert golden == EXPECTED_PREDRAW_GOLDEN


def test_rollout_is_per_origin_reproducible_and_crn_model_id_independent() -> None:
    torch = pytest.importorskip("torch")
    kwargs = {
        "blend_weights": [0.5] * 9,
        "base_seed": 1729,
        "source_id": "wqp",
        "site_id": "site-A",
        "origin_year_month": "2020-09",
        "device": torch.device("cpu"),
    }
    first = rollout_origin_samples(_model(), _window(), **kwargs)
    second = rollout_origin_samples(_model(), _window(), **kwargs)

    assert first.origin_seed_hex == second.origin_seed_hex
    assert first.predraw_sha256 == second.predraw_sha256
    assert np.array_equal(first.state_samples, second.state_samples)
    assert np.array_equal(first.irc_samples, second.irc_samples)


def test_rollout_batch_512_kernel_is_origin_batch_invariant() -> None:
    torch = pytest.importorskip("torch")
    windows = np.stack([_window(), _window()]).astype(np.float32)
    keys = [("wqp", "site-A", "2020-09"), ("wqp", "site-B", "2020-09")]
    together = rollout_origin_batch(
        _model(),
        windows,
        blend_weights=[0.5] * 9,
        base_seed=1729,
        origin_keys=keys,
        device=torch.device("cpu"),
    )
    separate = [
        rollout_origin_batch(
            _model(),
            windows[index : index + 1],
            blend_weights=[0.5] * 9,
            base_seed=1729,
            origin_keys=[key],
            device=torch.device("cpu"),
        )[0]
        for index, key in enumerate(keys)
    ]

    for batched, single in zip(together, separate, strict=True):
        assert batched.predraw_sha256 == single.predraw_sha256
        assert np.array_equal(batched.state_samples, single.state_samples)
        assert np.array_equal(batched.irc_samples, single.irc_samples)


def test_rollout_left_preserves_target_unavailable_and_failure_rows(tmp_path: Path) -> None:
    torch = pytest.importorskip("torch")
    success = build_closure_rollouts(
        _sequence(),
        _common(),
        model=_model(),
        blend_weights=[1.0] * 9,
        model_id="P0",
        base_seed=1729,
        device=torch.device("cpu"),
        expected_evaluation_units=3,
    )

    assert success.columns.tolist() == list(ROLLOUT_COLUMNS)
    assert len(success) == 3
    assert success["target_evaluable"].tolist() == [True, False, True]
    assert set(success["prediction_status"]) == {"success"}
    assert success["raw_bloom_score"].notna().all()
    assert all(len(values) == 128 for values in success["irc_samples"])
    count, digest = origin_rng_records_sha256(success)
    assert count == 1
    assert len(digest) == 64

    failed = build_closure_rollouts(
        _sequence(status="input_history_unavailable", reason="missing_history_state"),
        _common(),
        model=_model(),
        blend_weights=[1.0] * 9,
        model_id="P0",
        base_seed=1729,
        device=torch.device("cpu"),
        expected_evaluation_units=3,
    )
    assert len(failed) == 3
    assert set(failed["prediction_status"]) == {"sequence_unavailable"}
    assert set(failed["failure_reason"]) == {
        "sequence_input_history_unavailable_missing_history_state"
    }
    assert failed["target_evaluable"].tolist() == [True, False, True]
    assert failed.iloc[0]["irc_samples"] is None
    assert failed["origin_seed_hex"].str.len().eq(32).all()
    assert failed["predraw_sha256"].str.len().eq(64).all()
    assert origin_rng_records_sha256(failed)[0] == 1

    unavailable_model = build_closure_rollouts(
        _sequence(),
        _common(),
        model=None,
        blend_weights=None,
        model_id="P0",
        base_seed=1729,
        device=torch.device("cpu"),
        model_unavailable_reason="sequence_fit_rows_unavailable",
        expected_evaluation_units=3,
    )
    assert set(unavailable_model["prediction_status"]) == {"model_unavailable"}
    assert set(unavailable_model["failure_reason"]) == {"sequence_fit_rows_unavailable"}
    sample_array = rollout_arrow_table(unavailable_model).column("sample_yN").combine_chunks()
    assert sample_array.null_count == 0
    assert sample_array.values.null_count == 3 * 128

    mixed = pd.concat(
        [success.iloc[[0]], unavailable_model.iloc[[1]]],
        ignore_index=True,
    )
    output = tmp_path / "mixed_rollout.parquet"
    write_rollout_parquet(mixed, output)
    restored = pq.read_table(output)
    restored_samples = restored.column("sample_yN").combine_chunks()
    assert restored.schema.field("sample_yN").type == pa.list_(pa.float32(), 128)
    assert restored_samples.null_count == 0
    assert restored_samples.values.null_count == 128
    assert np.allclose(restored_samples[0].as_py(), mixed.iloc[0]["sample_yN"])
    assert restored_samples[1].as_py() == [None] * 128
    restored_irc = restored.column("irc_samples").combine_chunks()
    assert restored.schema.field("irc_samples").type == pa.list_(pa.float64(), 128)
    assert restored_irc.null_count == 0
    assert restored_irc.values.null_count == 128
    assert np.allclose(restored_irc[0].as_py(), mixed.iloc[0]["irc_samples"])
    assert restored_irc[1].as_py() == [None] * 128
    assert restored.column("raw_bloom_score").null_count == 1
    assert not output.with_suffix(output.suffix + ".tmp").exists()


def test_rollout_preserves_sequence_model_unavailable_cause_over_manifest_cause() -> None:
    torch = pytest.importorskip("torch")
    rollouts = build_closure_rollouts(
        _sequence(status="model_slot_unavailable", reason="anfis_model_slot_unavailable"),
        _common(),
        model=None,
        blend_weights=None,
        model_id="P0",
        base_seed=1729,
        device=torch.device("cpu"),
        model_unavailable_reason="sequence_fit_rows_unavailable",
        expected_evaluation_units=3,
    )
    assert set(rollouts["prediction_status"]) == {"model_unavailable"}
    assert set(rollouts["failure_reason"]) == {"anfis_model_slot_unavailable"}


def test_rollout_requires_explicit_unavailable_manifest_cause() -> None:
    torch = pytest.importorskip("torch")
    with pytest.raises(ValueError, match="explicit manifest failure reason"):
        build_closure_rollouts(
            _sequence(),
            _common(),
            model=None,
            blend_weights=None,
            model_id="P0",
            base_seed=1729,
            device=torch.device("cpu"),
            expected_evaluation_units=3,
        )


def test_rollout_propagates_technical_model_errors() -> None:
    torch = pytest.importorskip("torch")

    class BrokenModel(torch.nn.Module):
        def forward(self, _: Any) -> tuple[Any, Any]:
            raise RuntimeError("technical model failure")

    with pytest.raises(RuntimeError, match="technical model failure"):
        build_closure_rollouts(
            _sequence(),
            _common(),
            model=BrokenModel(),
            blend_weights=[1.0] * 9,
            model_id="P0",
            base_seed=1729,
            device=torch.device("cpu"),
            expected_evaluation_units=3,
        )


@pytest.mark.parametrize(("mu_value", "logvar_value"), [(np.nan, 0.0), (0.0, np.inf)])
def test_rollout_rejects_nonfinite_model_distribution_parameters(
    mu_value: float,
    logvar_value: float,
) -> None:
    torch = pytest.importorskip("torch")

    class NonfiniteModel(torch.nn.Module):
        def forward(self, x: Any) -> tuple[Any, Any]:
            shape = (x.shape[0], 9)
            return (
                torch.full(shape, mu_value, dtype=torch.float32, device=x.device),
                torch.full(shape, logvar_value, dtype=torch.float32, device=x.device),
            )

    with pytest.raises(ValueError, match="nonfinite mu/logvar"):
        build_closure_rollouts(
            _sequence(),
            _common(),
            model=NonfiniteModel(),
            blend_weights=[1.0] * 9,
            model_id="P0",
            base_seed=1729,
            device=torch.device("cpu"),
            expected_evaluation_units=3,
        )


def test_rollout_arrow_schema_has_nine_float32_and_one_float64_fixed_lists() -> None:
    torch = pytest.importorskip("torch")
    rollouts = build_closure_rollouts(
        _sequence(),
        _common(),
        model=_model(),
        blend_weights=[1.0] * 9,
        model_id="P0",
        base_seed=1729,
        device=torch.device("cpu"),
        expected_evaluation_units=3,
    )
    table = rollout_arrow_table(rollouts)

    for column in SAMPLE_COLUMNS:
        field = table.schema.field(column)
        assert pa.types.is_fixed_size_list(field.type)
        assert field.type.list_size == 128
        assert field.type.value_type == pa.float32()
    irc = table.schema.field("irc_samples")
    assert pa.types.is_fixed_size_list(irc.type)
    assert irc.type.list_size == 128
    assert irc.type.value_type == pa.float64()
    assert table.schema.field("raw_bloom_score").type == pa.float64()


def test_rollout_constants_match_authoritative_runtime() -> None:
    validate_rollout_runtime_contract(load_yaml_mapping(DEFAULT_RUNTIME_CONFIG))


def test_rollout_runtime_rejects_cpu_policy_drift() -> None:
    runtime = copy.deepcopy(load_yaml_mapping(DEFAULT_RUNTIME_CONFIG))
    runtime["cpu_execution_policy"]["torch_num_threads"] = 2
    with pytest.raises(ValueError, match="CPU execution policy"):
        validate_rollout_runtime_contract(runtime)


def _temporal_manifest_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    available: bool,
) -> tuple[
    dict[str, Any],
    dict[str, Path],
    list[dict[str, object]],
    list[dict[str, object]],
    FitAvailability,
]:
    from src.experiments import build_closure_pipe_sequences as sequence_module
    from src.experiments import rollout_closure_pipe as rollout_module

    monkeypatch.setattr(sequence_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(rollout_module, "PROJECT_ROOT", tmp_path)
    script_path = tmp_path / "src/experiments/train_closure_pipe.py"
    sequence_path = tmp_path / "data/sequence.parquet"
    for path, content in ((script_path, b"trainer"), (sequence_path, b"sequence")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    script_record = _file_record(script_path)
    input_records = [script_record, _file_record(sequence_path)]
    source_records = [script_record]
    artifact_paths = {
        name: tmp_path / f"artifacts/{name}.artifact"
        for name in (*MODEL_ARTIFACT_OUTPUT_NAMES, "manifest")
    }
    emitted_names = MODEL_ARTIFACT_OUTPUT_NAMES if available else ("report",)
    for name in emitted_names:
        path = artifact_paths[name]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(name.encode("utf-8"))
    outputs: list[dict[str, object]] = []
    for name in emitted_names:
        record: dict[str, object] = dict(_file_record(artifact_paths[name]))
        if name == "model":
            record["artifact_role"] = "final_model_with_locked_output_blend"
        elif name == "checkpoint":
            record["artifact_role"] = "raw_best_checkpoint"
        elif name == "report" and not available:
            record["artifact_role"] = "report"
        outputs.append(record)
    fit_availability = FitAvailability(
        available=available,
        failure_reason="" if available else "sequence_fit_rows_unavailable",
        fit_status_counts={"success": 9413} if available else {"model_slot_unavailable": 8352},
        failure_reason_counts={}
        if available
        else {"insufficient_eligible_training_rows": 8352},
    )
    payload: dict[str, Any] = {
        "manifest_version": "closure_pipe_model_manifest_v1",
        "status": "completed",
        "generated_at_utc": "2026-08-03T12:00:00+00:00",
        "slot_status": "available" if available else "model_unavailable",
        "fit_status": "passed" if available else "not_attempted",
        "failure_reason": "" if available else "sequence_fit_rows_unavailable",
        "model_artifact_emitted": available,
        "failed_slot_replaced": False,
        "replacement_used": False,
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": "P0",
        "base_seed": 1729,
        "device": "cpu",
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "completion_marker_written_last": True,
        "cpu_execution_policy": expected_cpu_execution_policy_record(),
        "script": script_record,
        "source_code": source_records,
        "inputs": input_records,
        "config": fixed_profile(),
        "input_state_mapping": MODEL_STATE_MAPPINGS["P0"],
        "target_state_mapping": MODEL_STATE_MAPPINGS["P0"],
        "target_to_next_input_mapping": TARGET_TO_NEXT_INPUT_MAPPING,
        "outputs": outputs,
    }
    if available:
        payload.update(
            {
                "selection": {
                    "best_epoch": 1,
                    "best_model_selection_objective": 0.25,
                    "checkpoint_role": "raw_best_unblended_model_state",
                    "final_blend_stage": "once_after_raw_best_restore",
                },
                "batch_order": {
                    "algorithm": "torch_randperm_cpu_generator",
                    "epoch_seed": "base_seed_plus_one_based_epoch",
                    "record_serialization": "compact_json_utf8_lf_per_batch",
                    "records": [
                        {"epoch": 1, "batch_order_sha256": "a" * 64}
                    ],
                },
                "row_counts": {
                    "training_windows": 8352,
                    "model_selection_windows": 1061,
                    "calibration_windows_not_used_for_fit": 319,
                    "test_windows": 0,
                    "holdout_windows": 0,
                },
            }
        )
    else:
        payload.update(
            {
                "fit_status_counts": fit_availability.fit_status_counts,
                "failure_reason_counts": fit_availability.failure_reason_counts,
            }
        )
    return payload, artifact_paths, input_records, source_records, fit_availability


def test_temporal_model_manifest_binds_all_available_outputs_and_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, paths, inputs, sources, availability = _temporal_manifest_bundle(
        tmp_path,
        monkeypatch,
        available=True,
    )
    assert validate_temporal_model_manifest(
        payload,
        model_id="P0",
        base_seed=1729,
        artifact_paths=paths,
        expected_input_records=inputs,
        expected_source_code_records=sources,
        fit_availability=availability,
    )
    payload["unexpected"] = True
    with pytest.raises(ValueError, match="top-level dialect"):
        validate_temporal_model_manifest(
            payload,
            model_id="P0",
            base_seed=1729,
            artifact_paths=paths,
            expected_input_records=inputs,
            expected_source_code_records=sources,
            fit_availability=availability,
        )
    payload.pop("unexpected")
    payload["outputs"] = list(payload["outputs"])[:-1]
    with pytest.raises(ValueError, match="outputs set/order drifted"):
        validate_temporal_model_manifest(
            payload,
            model_id="P0",
            base_seed=1729,
            artifact_paths=paths,
            expected_input_records=inputs,
            expected_source_code_records=sources,
            fit_availability=availability,
        )


def test_temporal_model_manifest_rejects_stale_input_config_or_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, paths, inputs, sources, availability = _temporal_manifest_bundle(
        tmp_path,
        monkeypatch,
        available=True,
    )
    payload["config"] = {**fixed_profile(), "hidden_dim": 95}
    with pytest.raises(ValueError, match="section 'config' drifted"):
        validate_temporal_model_manifest(
            payload,
            model_id="P0",
            base_seed=1729,
            artifact_paths=paths,
            expected_input_records=inputs,
            expected_source_code_records=sources,
            fit_availability=availability,
        )
    payload["config"] = fixed_profile()
    payload["cpu_execution_policy"] = {
        **expected_cpu_execution_policy_record(),
        "torch_num_threads_observed": 2,
    }
    with pytest.raises(ValueError, match="cpu_execution_policy.*drifted"):
        validate_temporal_model_manifest(
            payload,
            model_id="P0",
            base_seed=1729,
            artifact_paths=paths,
            expected_input_records=inputs,
            expected_source_code_records=sources,
            fit_availability=availability,
        )
    payload["cpu_execution_policy"] = expected_cpu_execution_policy_record()
    payload["input_state_mapping"] = {**MODEL_STATE_MAPPINGS["P0"], "yT": "yT"}
    with pytest.raises(ValueError, match="section 'input_state_mapping' drifted"):
        validate_temporal_model_manifest(
            payload,
            model_id="P0",
            base_seed=1729,
            artifact_paths=paths,
            expected_input_records=inputs,
            expected_source_code_records=sources,
            fit_availability=availability,
        )
    payload["input_state_mapping"] = MODEL_STATE_MAPPINGS["P0"]
    sequence_path = tmp_path / "data/sequence.parquet"
    sequence_path.write_bytes(b"new sequence")
    with pytest.raises(ValueError, match="differs from physical bytes"):
        validate_temporal_model_manifest(
            payload,
            model_id="P0",
            base_seed=1729,
            artifact_paths=paths,
            expected_input_records=inputs,
            expected_source_code_records=sources,
            fit_availability=availability,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("artifact_role", "raw_best_checkpoint", "locked final blended model"),
        ("device", "cuda", "locked CPU runtime"),
        ("base_seed", 1729.9, "identity differs"),
        ("config", {"hidden_dim": 95}, "fixed config drifted"),
        ("input_state_mapping", {}, "mapping 'input_state_mapping' drifted"),
    ],
)
def test_loaded_model_rejects_final_artifact_metadata_drift(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    torch = pytest.importorskip("torch")
    payload: dict[str, object] = {
        "model_version": "closure_pipe_temporal_v1",
        "artifact_role": "final_model_with_locked_output_blend",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": "P0",
        "base_seed": 1729,
        "device": "cpu",
        "input_columns": list(INPUT_COLUMNS),
        "target_columns": list(TARGET_COLUMNS),
        "config": fixed_profile(),
        "input_state_mapping": MODEL_STATE_MAPPINGS["P0"],
        "target_state_mapping": MODEL_STATE_MAPPINGS["P0"],
        "target_to_next_input_mapping": TARGET_TO_NEXT_INPUT_MAPPING,
    }
    payload[field] = value
    path = tmp_path / f"{field}.pt"
    torch.save(payload, path)
    with pytest.raises(ValueError, match=message):
        _load_model(
            path,
            checkpoint_path=tmp_path / "checkpoint.pt",
            blend_weights_path=tmp_path / "blend_weights.csv",
            model_id="P0",
            base_seed=1729,
            device=torch.device("cpu"),
        )


def test_loaded_model_requires_locked_grid_and_blend_csv_concordance(tmp_path: Path) -> None:
    torch = pytest.importorskip("torch")
    target_names = [column.removeprefix("target_") for column in TARGET_COLUMNS]
    payload: dict[str, object] = {
        "model_version": "closure_pipe_temporal_v1",
        "artifact_role": "final_model_with_locked_output_blend",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": "P0",
        "base_seed": 1729,
        "device": "cpu",
        "input_columns": list(INPUT_COLUMNS),
        "target_columns": list(TARGET_COLUMNS),
        "config": fixed_profile(),
        "input_state_mapping": MODEL_STATE_MAPPINGS["P0"],
        "target_state_mapping": MODEL_STATE_MAPPINGS["P0"],
        "target_to_next_input_mapping": TARGET_TO_NEXT_INPUT_MAPPING,
        "output_blend_weights": {target: 0.42 for target in target_names},
    }
    model_path = tmp_path / "model.pt"
    blend_path = tmp_path / "blend_weights.csv"
    torch.save(payload, model_path)
    with pytest.raises(ValueError, match="locked grid"):
        _load_model(
            model_path,
            checkpoint_path=tmp_path / "checkpoint.pt",
            blend_weights_path=blend_path,
            model_id="P0",
            base_seed=1729,
            device=torch.device("cpu"),
        )

    payload["output_blend_weights"] = {target: 0.5 for target in target_names}
    torch.save(payload, model_path)
    pd.DataFrame(
        {
            "target": target_names,
            "blend_weight": [0.65, *([0.5] * 8)],
            "validation_rows": [1061] * 9,
            "validation_mae": [0.1] * 9,
            "validation_rmse": [0.2] * 9,
            "selection_metric": ["balanced"] * 9,
            "selection_objective": [1.0] * 9,
        }
    ).to_csv(blend_path, index=False)
    with pytest.raises(ValueError, match="differ from the CSV"):
        _load_model(
            model_path,
            checkpoint_path=tmp_path / "checkpoint.pt",
            blend_weights_path=blend_path,
            model_id="P0",
            base_seed=1729,
            device=torch.device("cpu"),
        )


def test_loaded_model_requires_exact_unblended_raw_checkpoint_state(tmp_path: Path) -> None:
    torch = pytest.importorskip("torch")
    target_names = [column.removeprefix("target_") for column in TARGET_COLUMNS]
    state = {"weight": torch.tensor([1.0, 2.0], dtype=torch.float32)}
    artifact_base: dict[str, object] = {
        "model_version": "closure_pipe_temporal_v1",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": "P0",
        "base_seed": 1729,
        "device": "cpu",
        "config": fixed_profile(),
        "input_columns": list(INPUT_COLUMNS),
        "target_columns": list(TARGET_COLUMNS),
        "input_state_mapping": MODEL_STATE_MAPPINGS["P0"],
        "target_state_mapping": MODEL_STATE_MAPPINGS["P0"],
        "target_to_next_input_mapping": TARGET_TO_NEXT_INPUT_MAPPING,
        "best_epoch": 3,
        "best_model_selection_objective": 0.25,
        "model_state_dict": state,
    }
    model_path = tmp_path / "model.pt"
    checkpoint_path = tmp_path / "checkpoint.pt"
    blend_path = tmp_path / "blend_weights.csv"
    torch.save(
        {
            **artifact_base,
            "artifact_role": "final_model_with_locked_output_blend",
            "output_blend_weights": {target: 0.5 for target in target_names},
        },
        model_path,
    )
    pd.DataFrame(
        {
            "target": target_names,
            "blend_weight": [0.5] * len(target_names),
            "validation_rows": [1061] * len(target_names),
            "validation_mae": [0.1] * len(target_names),
            "validation_rmse": [0.2] * len(target_names),
            "selection_metric": ["balanced"] * len(target_names),
            "selection_objective": [1.0] * len(target_names),
        }
    ).to_csv(blend_path, index=False)

    torch.save(
        {
            **artifact_base,
            "artifact_role": "raw_best_checkpoint",
            "output_blend_weights": {target: 0.5 for target in target_names},
        },
        checkpoint_path,
    )
    with pytest.raises(ValueError, match="forbidden blend state"):
        _load_model(
            model_path,
            checkpoint_path=checkpoint_path,
            blend_weights_path=blend_path,
            model_id="P0",
            base_seed=1729,
            device=torch.device("cpu"),
        )

    torch.save(
        {
            **artifact_base,
            "artifact_role": "raw_best_checkpoint",
            "model_state_dict": {
                "weight": torch.tensor([1.0, 3.0], dtype=torch.float32)
            },
        },
        checkpoint_path,
    )
    with pytest.raises(ValueError, match="tensor 'weight' differs"):
        _load_model(
            model_path,
            checkpoint_path=checkpoint_path,
            blend_weights_path=blend_path,
            model_id="P0",
            base_seed=1729,
            device=torch.device("cpu"),
        )

def test_temporal_model_manifest_requires_exact_unavailable_report_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, paths, inputs, sources, availability = _temporal_manifest_bundle(
        tmp_path,
        monkeypatch,
        available=False,
    )
    assert not validate_temporal_model_manifest(
        payload,
        model_id="P0",
        base_seed=1729,
        artifact_paths=paths,
        expected_input_records=inputs,
        expected_source_code_records=sources,
        fit_availability=availability,
    )
    payload["unexpected"] = True
    with pytest.raises(ValueError, match="top-level dialect"):
        validate_temporal_model_manifest(
            payload,
            model_id="P0",
            base_seed=1729,
            artifact_paths=paths,
            expected_input_records=inputs,
            expected_source_code_records=sources,
            fit_availability=availability,
        )
    payload.pop("unexpected")
    payload["outputs"] = []
    with pytest.raises(ValueError, match="outputs set/order drifted"):
        validate_temporal_model_manifest(
            payload,
            model_id="P0",
            base_seed=1729,
            artifact_paths=paths,
            expected_input_records=inputs,
            expected_source_code_records=sources,
            fit_availability=availability,
        )
    payload, paths, inputs, sources, availability = _temporal_manifest_bundle(
        tmp_path,
        monkeypatch,
        available=False,
    )
    paths["model"].write_bytes(b"orphan")
    with pytest.raises(ValueError, match="stale fit outputs"):
        validate_temporal_model_manifest(
            payload,
            model_id="P0",
            base_seed=1729,
            artifact_paths=paths,
            expected_input_records=inputs,
            expected_source_code_records=sources,
            fit_availability=availability,
        )


def test_rollout_bundle_preflight_rejects_final_or_temporary_evidence(
    tmp_path: Path,
) -> None:
    output = tmp_path / "rollout.parquet"
    manifest = tmp_path / "manifest.json"
    assert_rollout_outputs_absent((output, manifest))
    manifest.write_bytes(b"partial")
    with pytest.raises(ValueError, match="overwrite is forbidden"):
        assert_rollout_outputs_absent((output, manifest))
    manifest.unlink()
    output.with_suffix(".parquet.tmp").write_bytes(b"interrupted")
    with pytest.raises(ValueError, match="overwrite is forbidden"):
        assert_rollout_outputs_absent((output, manifest))
    output.with_suffix(".parquet.tmp").unlink()
    pointer = Path(f"{output.as_posix()}.dvc")
    pointer.write_bytes(b"outs: []")
    with pytest.raises(ValueError, match="overwrite is forbidden"):
        assert_rollout_outputs_absent((output, manifest))


def test_main_stops_at_external_gate_before_rollout_io(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.experiments import rollout_closure_pipe as module

    class GateStopped(RuntimeError):
        pass

    fake_lock = types.ModuleType(
        "src.experiments.closure_development_runtime_temporal_validation_manifest_patch"
    )

    def stop_gate(*, device: str | None = None, **_: object) -> dict[str, object]:
        assert device == "cpu"
        raise GateStopped

    setattr(
        fake_lock,
        "require_development_fit_authorized_with_temporal_validation_manifest_patch",
        stop_gate,
    )
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


@pytest.mark.parametrize("model_id", ["P0", "P1"])
def test_main_propagates_temporal_validation_builder_domains_before_sequence_io(
    model_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import rollout_closure_pipe as module

    class ContractObserved(RuntimeError):
        pass

    events: list[str] = []
    historical = {
        "path": "src/experiments/build_closure_pipe_sequences.py",
        "bytes": 110_034,
        "sha256": "dc500d94c8ca4b3705d2cb849a037524e33915624cd86f9d355e5c4eebb347f6",
    }
    current = {
        "path": "src/experiments/build_closure_pipe_sequences.py",
        "bytes": 1,
        "sha256": "1" * 64,
    }
    authority: dict[str, object] = {
        "p0_artifact_builder_record": historical,
        "current_runtime_builder_record": current,
    }
    fake_lock = types.ModuleType(
        "src.experiments.closure_development_runtime_temporal_validation_manifest_patch"
    )

    def gate(*, device: str | None = None) -> dict[str, object]:
        assert device == "cpu"
        events.append("gate")
        return authority

    setattr(
        fake_lock,
        "require_development_fit_authorized_with_temporal_validation_manifest_patch",
        gate,
    )
    monkeypatch.setitem(sys.modules, fake_lock.__name__, fake_lock)
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: Namespace(model_id=model_id, base_seed=1729, device="cpu"),
    )

    def builder_records(value: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        assert value is authority
        events.append("builder-authority")
        return historical, current

    monkeypatch.setattr(
        module,
        "builder_records_from_temporal_validation_authority",
        builder_records,
    )
    monkeypatch.setattr(module, "load_yaml_mapping", lambda path: {})
    monkeypatch.setattr(module, "validate_rollout_runtime_contract", lambda runtime: None)
    monkeypatch.setattr(
        module,
        "configure_torch_cpu_execution_policy",
        lambda runtime: expected_cpu_execution_policy_record(),
    )
    monkeypatch.setattr(module, "validate_temporal_seed", lambda *args: None)
    monkeypatch.setattr(module, "configure_deterministic_runtime", lambda *args: "cpu")
    monkeypatch.setattr(module, "assert_rollout_outputs_absent", lambda paths: None)

    def collect(**kwargs: Any) -> None:
        assert kwargs == {
            "model_id": model_id,
            "base_seed": 1729,
            "artifact_builder_record": historical if model_id == "P0" else current,
            "current_runtime_builder_record": current,
        }
        events.append("sequence-contract")
        raise ContractObserved

    monkeypatch.setattr(module, "collect_sequence_input_contract", collect)
    reads: list[object] = []
    monkeypatch.setattr(pd, "read_parquet", lambda *args, **kwargs: reads.append((args, kwargs)))

    with pytest.raises(ContractObserved):
        module.main()
    assert events == ["gate", "builder-authority", "sequence-contract"]
    assert reads == []
