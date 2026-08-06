from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import types
from argparse import Namespace
from pathlib import Path
from typing import Any, Mapping, cast

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.experiments.build_closure_pipe_sequences import (
    ANFIS_MODULE_ARTIFACT_TOKENS,
    ANFIS_MODULES,
    ANFIS_REQUIRED_SOURCE_PATHS,
    DEFAULT_RUNTIME_CONFIG,
    INPUT_COLUMNS,
    SEQUENCE_COLUMNS,
    SURFACE_ID,
    TARGET_COLUMNS,
    _file_record,
    assert_sequence_outputs_absent,
    build_closure_pipe_sequences,
    sequence_arrow_table,
    validate_sequence_runtime_contract,
    validate_state_slot_manifest,
    write_sequence_parquet,
)
from src.experiments.closure_contract import load_yaml_mapping
from src.experiments.closure_runtime_contract import anfis_module_substreams
from src.experiments.closure_runtime_contract import EXPECTED_CPU_EXECUTION_POLICY


def _common_origin() -> pd.DataFrame:
    rows = []
    for horizon, target in ((1, "2020-10"), (2, "2020-11"), (3, "2020-12")):
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
            }
        )
    return pd.DataFrame(rows)


def _state_frame() -> pd.DataFrame:
    months = pd.period_range("2019-10", "2020-12", freq="M").astype(str)
    frame = pd.DataFrame(
        {
            "source_id": "wqp",
            "site_id": "site-A",
            "year_month": months,
            # The first context months deliberately precede the endpoint role.
            "time_role": ["training"] * 3 + ["model_selection"] * 12,
            "delta_previous_month_missing": [True] + [False] * 14,
        }
    )
    step = np.arange(len(frame), dtype=np.float64) / 100.0
    frame["yN"] = 0.10 + step
    frame["yF"] = 0.20 + step
    frame["yT"] = 0.99  # Poisoned full-Chl-a sibling must never be selected.
    frame["yT_no_chla"] = 0.30 + step
    frame["sigma_N"] = 0.11
    frame["sigma_F"] = 0.12
    frame["sigma_T"] = 0.98
    frame["sigma_T_no_chla"] = 0.13
    frame["delta_yN"] = -0.10
    frame["delta_yF"] = 0.05
    frame["delta_yT"] = 0.97
    frame["delta_yT_no_chla"] = -0.20
    frame["yN_adaptive"] = frame["yN"] + 0.01
    frame["yF_adaptive"] = frame["yF"] + 0.01
    frame["yT_adaptive"] = 0.96
    frame["yT_no_chla_adaptive"] = frame["yT_no_chla"] + 0.01
    frame["sigma_N_adaptive"] = 0.21
    frame["sigma_F_adaptive"] = 0.22
    frame["sigma_T_adaptive"] = 0.95
    frame["sigma_T_no_chla_adaptive"] = 0.23
    frame["delta_yN_adaptive"] = -0.09
    frame["delta_yF_adaptive"] = 0.06
    frame["delta_yT_adaptive"] = 0.94
    frame["delta_yT_no_chla_adaptive"] = -0.19
    frame["irc1"] = 0.99
    frame["x_irc1"] = 0.99
    return frame


def _anfis_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    state_path: Path,
) -> dict[str, object]:
    from src.experiments import build_closure_pipe_sequences as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    runtime_config = Path("configs/runtime.yaml")
    runtime_schema = Path("configs/runtime.schema.json")
    runtime_lock = Path("reports/runtime_lock.json")
    runtime_lock_schema = Path("configs/runtime_lock.schema.json")
    role_paths = {
        "development_runtime_config": runtime_config,
        "development_runtime_schema": runtime_schema,
        "development_runtime_lock": runtime_lock,
        "development_runtime_lock_schema": runtime_lock_schema,
        "common_origin": Path("data/common.parquet"),
        "common_origin_completion_manifest": Path("reports/common.json"),
        "restored_panel": Path("data/panel.parquet"),
        "restored_expert_anchor": Path("data/expert.parquet"),
        "holdout_assignment": module.DEFAULT_ASSIGNMENT,
        "holdout_manifest": module.DEFAULT_HOLDOUT_MANIFEST,
        "protocol_lock": module.DEFAULT_PROTOCOL_LOCK,
        **dict(zip(module.ANFIS_DEPENDENCY_ROLES[11:], map(Path, ANFIS_REQUIRED_SOURCE_PATHS), strict=True)),
    }
    runtime_payload = {
        "implementation_lock": {
            "lock_manifest_path": runtime_lock.as_posix(),
            "lock_schema_path": runtime_lock_schema.as_posix(),
        },
        "authority": {
            "common_origin_manifest_path": role_paths["common_origin"].as_posix(),
            "common_origin_completion_manifest_path": role_paths[
                "common_origin_completion_manifest"
            ].as_posix(),
        },
        "anfis": {
            "primary_module_features": {
                "ANFIS-N": ["tp", "tn", "ratio"],
                "ANFIS-F": ["do", "ph", "turbidity", "secchi"],
                "ANFIS-T-no-current": ["temperature"],
            },
            "fixed_configuration": {
                "train_rows_per_module": 4096,
                "memberships_per_input": 3,
                "epochs": 60,
                "min_output_standard_deviation": 0.0001,
            },
            "uncertainty_proxy": {
                "rule_count_by_module": {
                    "ANFIS-N": 27,
                    "ANFIS-F": 81,
                    "ANFIS-T-no-current": 3,
                }
            },
            "sampling": {
                "persisted_sample_columns": [
                    "source_id",
                    "site_id",
                    "year_month",
                    "module",
                    "module_seed",
                    "rank_sha256",
                ]
            },
            "source_projection": {
                "panel_path": role_paths["restored_panel"].as_posix(),
                "expert_anchor_path": role_paths["restored_expert_anchor"].as_posix(),
            }
        },
        "artifacts": {
            "anfis_state_template": state_path.relative_to(tmp_path).as_posix(),
            "anfis_model_template": "models/{module}.pt",
            "anfis_sample_keys_template": "reports/{module}_sample.csv",
            "anfis_metrics_template": "reports/metrics.csv",
            "anfis_training_curve_template": "reports/curve.csv",
            "anfis_memberships_initial_template": "reports/memberships_initial.csv",
            "anfis_memberships_final_template": "reports/memberships_final.csv",
            "anfis_report_template": "reports/report.md",
            "anfis_lineage_audit_template": "reports/lineage.json",
        },
    }
    for relative in role_paths.values():
        physical = tmp_path / relative
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_bytes(relative.as_posix().encode("utf-8"))
    one_byte_role = "strict_expert_state_adapter"
    (tmp_path / role_paths[one_byte_role]).write_bytes(b"x")
    (tmp_path / runtime_config).write_text(json.dumps(runtime_payload), encoding="utf-8")
    dependencies = [
        {**_file_record(tmp_path / role_paths[role]), "role": role}
        for role in module.ANFIS_DEPENDENCY_ROLES
    ]
    script = {
        **_file_record(tmp_path / ANFIS_REQUIRED_SOURCE_PATHS[0]),
        "role": "generating_script",
    }
    inputs = [
        record for record in dependencies if record["role"] != "strict_anfis_state_adapter"
    ]
    config_record = _file_record(tmp_path / runtime_config)
    schema_record = _file_record(tmp_path / runtime_schema)
    lock_record = _file_record(tmp_path / runtime_lock)
    return {
        "development_fit_authorized": True,
        "cpu_execution_policy": {
            **EXPECTED_CPU_EXECUTION_POLICY,
            "torch_num_threads_observed": 1,
            "torch_num_interop_threads_observed": 1,
        },
        "script": script,
        "dependencies": dependencies,
        "inputs": inputs,
        "runtime": {
            "config_path": config_record["path"],
            "config_sha256": config_record["sha256"],
            "schema_path": schema_record["path"],
            "schema_sha256": schema_record["sha256"],
        },
        "authorization": {
            "lock_version": "closure_development_runtime_lock_v1",
            "status": "locked",
            "device": "cpu",
            "locked_repository_head": "a" * 40,
            "execution_head": "a" * 40,
            "published_ref": "origin/main",
            "published_head": "a" * 40,
            "remote_main_oid": "a" * 40,
            "locked_head_is_ancestor": True,
            "locked_parent_published_at_lock": True,
            "publication_verified": True,
            "tracking_ref_publication_verified": True,
            "remote_publication_verified": True,
            "canonical_origin_identity_verified": True,
            "component_count": 18,
            "planned_artifact_path_count": 20,
            "planned_artifact_paths_sha256": "c" * 64,
            "metadata_verified": True,
            "physical_artifacts_required": True,
            "physical_artifacts_verified": True,
            "common_origin_output_verified": True,
            "expert_state_output_verified": True,
            "restored_development_sources_verified": True,
            "dvc_remote_verified_at_lock": True,
            "dvc_remote_verified": True,
            "fit_authorization_predicates": {
                "payload_authorization_verified": True,
                "locked_parent_published_at_lock": True,
                "physical_artifacts_verified": True,
                "publication_verified": True,
                "live_git_remote_verified": True,
                "canonical_origin_identity_verified": True,
                "common_origin_output_verified": True,
                "expert_state_output_verified": True,
                "restored_development_sources_verified": True,
                "dvc_remote_verified_at_lock": True,
                "locked_head_is_ancestor": True,
            },
            "payload_development_fit_authorized": True,
            "payload_evaluation_authorized": False,
            "payload_e0_u_authorized": False,
            "fit_authorized": True,
            "development_fit_authorized": True,
            "evaluation_authorized": False,
            "e0_u_authorized": False,
            "future_outcomes_accessed": False,
            "lock_path": lock_record["path"],
            "lock_sha256": lock_record["sha256"],
        },
    }


def _sample_frame(module: str, module_seed: int, rows: int) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for index in range(rows):
        key = ("wqp", f"site-{index:04d}", "2018-12")
        rank_payload = json.dumps(
            [module_seed, *key],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        records.append(
            {
                "source_id": key[0],
                "site_id": key[1],
                "year_month": key[2],
                "module": module,
                "module_seed": module_seed,
                "rank_sha256": hashlib.sha256(rank_payload).hexdigest(),
            }
        )
    return pd.DataFrame(records).sort_values(
        ["rank_sha256", "source_id", "site_id", "year_month"],
        kind="mergesort",
    ).reset_index(drop=True) if records else pd.DataFrame(
        columns=[
            "source_id",
            "site_id",
            "year_month",
            "module",
            "module_seed",
            "rank_sha256",
        ]
    )


def _sample_key_digest(frame: pd.DataFrame) -> str:
    digest = hashlib.sha256()
    for key in zip(
        frame["source_id"].astype(str),
        frame["site_id"].astype(str),
        frame["year_month"].astype(str),
        strict=True,
    ):
        key_bytes = json.dumps(
            list(key),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        digest.update(key_bytes)
        digest.update(b"\n")
    return digest.hexdigest()


def _anfis_outputs(
    tmp_path: Path,
    *,
    state_path: Path,
    dialect: str,
) -> list[dict[str, object]]:
    fitted = dialect != "unavailable_not_attempted"
    scientific = _anfis_scientific_fields(dialect=dialect)
    records: list[dict[str, object]] = []

    def add(relative: str, role: str, module: str | None = None) -> None:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.encode("utf-8"))
        record: dict[str, object] = {**_file_record(path), "role": role}
        if module is not None:
            record["module"] = module
        records.append(record)

    if fitted:
        if not state_path.is_file():
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_bytes(b"state")
        records.append({**_file_record(state_path), "role": "adaptive_no_current_state"})
    sampling = cast(dict[str, dict[str, Any]], scientific["sampling"])
    for module in ANFIS_MODULES:
        artifact_token = ANFIS_MODULE_ARTIFACT_TOKENS[module]
        if fitted:
            add(f"models/{artifact_token}.pt", "anfis_checkpoint", module)
        sample_path = tmp_path / f"reports/{artifact_token}_sample.csv"
        sample_path.parent.mkdir(parents=True, exist_ok=True)
        audit = sampling[module]
        _sample_frame(
            module,
            int(audit["module_seed"]),
            int(audit["selected_rows"]),
        ).to_csv(
            sample_path,
            index=False,
        )
        records.append({**_file_record(sample_path), "role": "sample_keys", "module": module})
    metrics_path = tmp_path / "reports/metrics.csv"
    pd.DataFrame(cast(list[dict[str, Any]], scientific["module_metrics"])).to_csv(
        metrics_path,
        index=False,
    )
    records.append({**_file_record(metrics_path), "role": "module_metrics"})
    if fitted:
        add("reports/curve.csv", "training_curve")
        add("reports/memberships_initial.csv", "memberships_initial")
        add("reports/memberships_final.csv", "memberships_final")
    add("reports/report.md", "report")
    add("reports/lineage.json", "lineage_audit")
    return records


def _anfis_scientific_fields(
    *,
    dialect: str,
    base_seed: int = 1729,
) -> dict[str, object]:
    substreams = anfis_module_substreams(base_seed)
    sampling: dict[str, dict[str, object]] = {}
    metrics: list[dict[str, object]] = []
    for index, module in enumerate(ANFIS_MODULES):
        selected_rows = 0 if dialect == "unavailable_not_attempted" and index == 0 else 4096
        excluded_nonfinite = 1000 if selected_rows == 0 else 10
        excluded_missingness = 2000 if selected_rows == 0 else 20
        eligible_rows = 2000 if selected_rows == 0 else 4970
        audit: dict[str, object] = {
            "input_rows": 5000,
            "excluded_nonfinite_target_rows": excluded_nonfinite,
            "excluded_missingness_rows": excluded_missingness,
            "eligible_universe_rows": eligible_rows,
            "eligible_universe_sha256": "a" * 64,
            "selected_rows": selected_rows,
            "selected_keys_sha256": _sample_key_digest(
                _sample_frame(module, substreams[module], selected_rows)
            ),
            "module": module,
            "base_seed": base_seed,
            "module_seed": substreams[module],
        }
        if selected_rows == 0:
            audit.update(
                {
                    "required_rows": 4096,
                    "replacement_used": False,
                    "failure_reason": "insufficient_eligible_training_rows",
                }
            )
        sampling[module] = audit
        if dialect == "unavailable_not_attempted":
            metrics.append(
                {
                    "module": module,
                    "status": "model_unavailable"
                    if selected_rows == 0
                    else "not_fitted_due_to_slot_unavailable",
                    "failure_reason": "insufficient_eligible_training_rows"
                    if selected_rows == 0
                    else "paired_slot_unavailable",
                    "base_seed": base_seed,
                    "module_seed": substreams[module],
                    "input_rows": 5000,
                    "excluded_nonfinite_target_rows": excluded_nonfinite,
                    "excluded_missingness_rows": excluded_missingness,
                    "eligible_universe_rows": eligible_rows,
                    "selected_rows": selected_rows,
                    "required_rows": 4096,
                    "replacement_used": False,
                    "fit_attempted": False,
                }
            )
        else:
            metrics.append(
                {
                    "module": module,
                    "status": "failed"
                    if dialect == "unavailable_failed" and index == 0
                    else "passed",
                    "base_seed": base_seed,
                    "module_seed": substreams[module],
                    "train_rows": 4096,
                    "prediction_rows": 10000,
                    "input_dimension": {"ANFIS-N": 3, "ANFIS-F": 4, "ANFIS-T-no-current": 1}[module],
                    "rule_count": {"ANFIS-N": 27, "ANFIS-F": 81, "ANFIS-T-no-current": 3}[module],
                    "epochs": 60,
                    "curve_initial_pre_update_loss": 1.0,
                    "curve_last_pre_update_loss": 0.6,
                    "minimum_curve_pre_update_loss": 0.5,
                    "final_checkpoint_loss": 0.4,
                    "quality_gate_output_standard_deviation": (
                        0.0
                        if dialect == "unavailable_failed" and index == 0
                        else 0.1
                    ),
                    "quality_gate_output_scope": "locked_hash_ranked_training_sample_4096",
                    "materialized_surface_output_standard_deviation": 0.2,
                    "maximum_parameter_delta": 0.2,
                    "centers_ordered": True,
                    "centers_in_unit_interval": True,
                }
            )
    full_join = {
        "filtered_anchor_rows": 10020,
        "filtered_panel_rows": 10010,
        "matched_rows": 10000,
        "unmatched_anchor_rows": 20,
        "unmatched_panel_rows": 10,
        "anchor_keys_sha256": "1" * 64,
        "panel_keys_sha256": "2" * 64,
        "matched_keys_sha256": "3" * 64,
        "unmatched_anchor_keys_sha256": "4" * 64,
        "unmatched_panel_keys_sha256": "5" * 64,
    }
    training_join = {
        **full_join,
        "filtered_anchor_rows": 5015,
        "filtered_panel_rows": 5005,
        "matched_rows": 5000,
        "unmatched_anchor_rows": 15,
        "unmatched_panel_rows": 5,
        "anchor_keys_sha256": "6" * 64,
        "panel_keys_sha256": "7" * 64,
        "matched_keys_sha256": "8" * 64,
        "unmatched_anchor_keys_sha256": "9" * 64,
        "unmatched_panel_keys_sha256": "0" * 64,
    }
    failed_modules = (
        [ANFIS_MODULES[0]]
        if dialect in {"unavailable_not_attempted", "unavailable_failed"}
        else []
    )
    result: dict[str, object] = {
        "generated_at_utc": "2026-08-03T12:00:00+00:00",
        "module_substreams": substreams,
        "panel_anchor_joins": {
            "training_candidates": training_join,
            "full_development": full_join,
        },
        "sampling": sampling,
        "module_metrics": metrics,
        "failed_modules": failed_modules,
        "planned_unmaterialized_heavy_outputs": [],
    }
    if dialect == "unavailable_not_attempted":
        result.update(
            {
                "counts": {
                    "state_rows": 0,
                    "joined_development_rows": 10000,
                    "joined_training_candidate_rows": 5000,
                    "development_locations": 10,
                    "unavailable_modules": 1,
                },
                "planned_unmaterialized_heavy_outputs": [
                    "state.parquet",
                    *(
                        f"models/{ANFIS_MODULE_ARTIFACT_TOKENS[module]}.pt"
                        for module in ANFIS_MODULES
                    ),
                ],
            }
        )
    else:
        result["counts"] = {
            "state_rows": 10000,
            "joined_development_rows": 10000,
            "joined_training_candidate_rows": 5000,
            "development_locations": 353,
            "delta_previous_month_missing": 25,
        }
    return result


def test_p0_sequence_uses_no_current_mapping_for_input_target_and_recycle() -> None:
    state = _state_frame()
    sequences, audit = build_closure_pipe_sequences(
        state,
        _common_origin(),
        model_id="P0",
        base_seed=None,
        expected_origin_count=1,
    )

    assert audit.intent_origins == 1
    assert audit.successful_origins == 1
    assert audit.delta_previous_month_missing_history_values == 1
    assert audit.delta_previous_month_missing_target_values == 0
    assert sequences.columns.tolist() == list(SEQUENCE_COLUMNS)
    row = sequences.iloc[0]
    assert row["sequence_status"] == "success"
    assert len(row["x_yT"]) == 12
    assert row["x_yT"][-1] == pytest.approx(float(state.loc[11, "yT_no_chla"]))
    assert row["target_yT"] == pytest.approx(float(state.loc[12, "yT_no_chla"]))
    assert row["target_sigma_T"] == pytest.approx(0.13)
    assert row["target_delta_yT"] == pytest.approx(-0.20)
    assert row["target_yT"] != pytest.approx(0.99)
    assert not any("irc" in column.lower() for column in sequences.columns)
    assert set(INPUT_COLUMNS).issubset(sequences.columns)
    assert set(TARGET_COLUMNS).issubset(sequences.columns)


def test_p1_sequence_uses_same_seed_scoped_no_current_mapping() -> None:
    state = _state_frame()
    sequences, _ = build_closure_pipe_sequences(
        state,
        _common_origin(),
        model_id="P1",
        base_seed=1729,
        expected_origin_count=1,
    )

    row = sequences.iloc[0]
    assert row["base_seed"] == 1729
    assert row["x_yT"][-1] == pytest.approx(float(state.loc[11, "yT_no_chla_adaptive"]))
    assert row["target_yT"] == pytest.approx(float(state.loc[12, "yT_no_chla_adaptive"]))
    assert row["target_delta_yT"] == pytest.approx(-0.19)


def test_missing_history_is_retained_as_fixed_shape_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    state = _state_frame().loc[lambda frame: ~frame["year_month"].eq("2020-03")]
    sequences, audit = build_closure_pipe_sequences(
        state,
        _common_origin(),
        model_id="P0",
        base_seed=None,
        expected_origin_count=1,
    )

    assert len(sequences) == 1
    assert audit.failed_origins == 1
    row = sequences.iloc[0]
    assert row["sequence_status"] == "input_history_unavailable"
    assert row["failure_reason"] == "missing_history_state"
    assert row["x_yN"] is None
    assert pd.isna(row["target_yN"])

    table = sequence_arrow_table(sequences)
    input_array = table.column("x_yN").combine_chunks()
    assert input_array.null_count == 0
    assert input_array.values.null_count == 12
    assert input_array[0].as_py() == [None] * 12
    assert table.column("target_yN").null_count == 1

    output = tmp_path / "failed_sequence.parquet"
    write_sequence_parquet(sequences, output)
    restored = pq.read_table(output)
    restored_input = restored.column("x_yN").combine_chunks()
    assert restored.schema.field("x_yN").type == pa.list_(pa.float32(), 12)
    assert restored_input.null_count == 0
    assert restored_input.values.null_count == 12
    assert restored_input[0].as_py() == [None] * 12
    assert restored.column("target_yN").null_count == 1
    assert restored.column("sequence_status")[0].as_py() == "input_history_unavailable"
    assert restored.column("failure_reason")[0].as_py() == "missing_history_state"
    assert not output.with_suffix(output.suffix + ".tmp").exists()


def test_sequence_arrow_schema_uses_fixed_size_float32_lists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    sequences, _ = build_closure_pipe_sequences(
        _state_frame(),
        _common_origin(),
        model_id="P0",
        base_seed=None,
        expected_origin_count=1,
    )
    table = sequence_arrow_table(sequences)

    for column in INPUT_COLUMNS:
        field = table.schema.field(column)
        assert pa.types.is_fixed_size_list(field.type)
        assert field.type.list_size == 12
        assert field.type.value_type == pa.float32()
    for column in TARGET_COLUMNS:
        assert table.schema.field(column).type == pa.float32()

    output = tmp_path / "sequence.parquet"
    write_sequence_parquet(sequences, output)
    restored_schema = pq.read_schema(output)
    assert restored_schema.field("x_yN").type == pa.list_(pa.float32(), 12)
    assert restored_schema.field("target_yN").type == pa.float32()
    restored = pq.read_table(output)
    assert np.allclose(
        restored.column("x_yN")[0].as_py(),
        sequences.iloc[0]["x_yN"],
    )
    assert restored.column("target_yN")[0].as_py() == pytest.approx(
        float(sequences.iloc[0]["target_yN"])
    )


def test_model_slot_unavailable_retains_origin_with_null_tensors() -> None:
    sequences, audit = build_closure_pipe_sequences(
        None,
        _common_origin(),
        model_id="P1",
        base_seed=1729,
        expected_origin_count=1,
        model_slot_failure_reason="insufficient_eligible_training_rows",
    )

    row = sequences.iloc[0]
    assert audit.failed_origins == 1
    assert row["sequence_status"] == "model_slot_unavailable"
    assert row["failure_reason"] == "insufficient_eligible_training_rows"
    assert row["x_yN"] is None
    input_array = sequence_arrow_table(sequences).column("x_yN").combine_chunks()
    assert input_array.null_count == 0
    assert input_array.values.null_count == 12


def test_sequence_requires_origin_and_target_to_share_endpoint_role() -> None:
    state = _state_frame()
    state.loc[state["year_month"].eq("2020-10"), "time_role"] = "calibration_threshold"

    with pytest.raises(ValueError, match="share the locked endpoint role"):
        build_closure_pipe_sequences(
            state,
            _common_origin(),
            model_id="P0",
            base_seed=None,
            expected_origin_count=1,
        )


def test_sequence_constants_match_authoritative_runtime() -> None:
    validate_sequence_runtime_contract(load_yaml_mapping(DEFAULT_RUNTIME_CONFIG))


def test_real_seed_1729_manifest_uses_explicit_historical_anfis_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    manifest_path = (
        module.PROJECT_ROOT
        / "reports/closure_v1/01_surface/anfis/seed_1729/manifest.json"
    )
    payload = cast(dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8")))
    dependencies = {
        str(record["role"]): dict(record)
        for record in cast(list[dict[str, Any]], payload["dependencies"])
    }
    historical_context = {
        "historical_source_records": {
            "generating_script": dict(cast(dict[str, Any], payload["script"])),
            "strict_anfis_state_adapter": dependencies["strict_anfis_state_adapter"],
            "runtime_lock_validator": dependencies["runtime_lock_validator"],
        },
        "historical_uppercase_artifact_paths": True,
    }
    authority: dict[str, Any] = {"authorization_effective": True}
    calls: list[tuple[Mapping[str, Any], Mapping[str, Any] | None]] = []
    fake_patch = types.ModuleType(
        "src.experiments.closure_p1_sequence_historical_anfis_patch"
    )

    class FakePatchError(Exception):
        pass

    def historical_context_adapter(
        manifest: Mapping[str, Any],
        *,
        authorization: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        calls.append((manifest, authorization))
        return historical_context

    setattr(fake_patch, "P1SequenceHistoricalAnfisPatchError", FakePatchError)
    setattr(fake_patch, "historical_seed_1729_anfis_context", historical_context_adapter)
    monkeypatch.setitem(sys.modules, fake_patch.__name__, fake_patch)

    assert validate_state_slot_manifest(
        payload,
        model_id="P1",
        base_seed=1729,
        state_path=(
            module.PROJECT_ROOT
            / "data/closure_v1/development/anfis/seed_1729/"
            "adaptive_no_current_state.parquet"
        ),
        consumer_authority=authority,
    ) == (True, "", False)
    assert calls == [(payload, authority)]


def test_historical_seed_1729_manifest_requires_explicit_consumer_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    manifest_path = (
        module.PROJECT_ROOT
        / "reports/closure_v1/01_surface/anfis/seed_1729/manifest.json"
    )
    payload = cast(dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8")))
    fake_patch = types.ModuleType(
        "src.experiments.closure_p1_sequence_historical_anfis_patch"
    )

    class FakePatchError(Exception):
        pass

    def require_authority(
        _: Mapping[str, Any],
        *,
        authorization: Mapping[str, Any] | None,
    ) -> None:
        if authorization is None:
            raise FakePatchError("explicit E0-MC authority is required")

    setattr(fake_patch, "P1SequenceHistoricalAnfisPatchError", FakePatchError)
    setattr(fake_patch, "historical_seed_1729_anfis_context", require_authority)
    monkeypatch.setitem(sys.modules, fake_patch.__name__, fake_patch)

    with pytest.raises(ValueError, match="valid published E0-MC authority"):
        validate_state_slot_manifest(
            payload,
            model_id="P1",
            base_seed=1729,
            state_path=(
                module.PROJECT_ROOT
                / "data/closure_v1/development/anfis/seed_1729/"
                "adaptive_no_current_state.parquet"
            ),
        )


def test_historical_anfis_adapter_does_not_mask_unexpected_defects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    manifest_path = (
        module.PROJECT_ROOT
        / "reports/closure_v1/01_surface/anfis/seed_1729/manifest.json"
    )
    payload = cast(dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8")))
    fake_patch = types.ModuleType(
        "src.experiments.closure_p1_sequence_historical_anfis_patch"
    )

    class FakePatchError(Exception):
        pass

    def unexpected_defect(
        _: Mapping[str, Any],
        *,
        authorization: Mapping[str, Any] | None,
    ) -> None:
        del authorization
        raise TypeError("unexpected adapter defect")

    setattr(fake_patch, "P1SequenceHistoricalAnfisPatchError", FakePatchError)
    setattr(fake_patch, "historical_seed_1729_anfis_context", unexpected_defect)
    monkeypatch.setitem(sys.modules, fake_patch.__name__, fake_patch)

    with pytest.raises(TypeError, match="unexpected adapter defect"):
        validate_state_slot_manifest(
            payload,
            model_id="P1",
            base_seed=1729,
            state_path=(
                module.PROJECT_ROOT
                / "data/closure_v1/development/anfis/seed_1729/"
                "adaptive_no_current_state.parquet"
            ),
            consumer_authority={"authorization_effective": True},
        )


def test_state_slot_manifest_requires_exact_available_physical_link(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_path = tmp_path / "state.parquet"
    payload: dict[str, Any] = {
        **_anfis_provenance(tmp_path, monkeypatch, state_path=state_path),
        **_anfis_scientific_fields(dialect="available"),
        "manifest_version": "closure_anfis_seed_manifest_v1",
        "status": "completed",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": "F1",
        "consumer_model_id": "P1",
        "base_seed": 1729,
        "slot_status": "available",
        "fit_status": "passed",
        "failure_reason": "",
        "state_artifact_emitted": True,
        "state_output_materialized": True,
        "checkpoint_outputs_materialized": True,
        "model_construction_attempted": True,
        "fit_attempted": True,
        "failed_slot_replaced": False,
        "replacement_used": False,
        "retain_failed_seed_slot": False,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "completion_marker_written_last": True,
        "outputs": _anfis_outputs(tmp_path, state_path=state_path, dialect="available"),
    }

    assert validate_state_slot_manifest(
        payload,
        model_id="P1",
        base_seed=1729,
        state_path=state_path,
    ) == (True, "", False)
    producer_manifest_bytes = (
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    ).encode("utf-8")
    round_tripped_payload = json.loads(producer_manifest_bytes)
    assert list(round_tripped_payload["module_metrics"][0]) != pd.read_csv(
        tmp_path / "reports/metrics.csv"
    ).columns.tolist()
    assert validate_state_slot_manifest(
        round_tripped_payload,
        model_id="P1",
        base_seed=1729,
        state_path=state_path,
    ) == (True, "", False)
    wrong_ref = copy.deepcopy(round_tripped_payload)
    wrong_ref["authorization"]["published_ref"] = "refs/remotes/origin/main"
    with pytest.raises(ValueError, match="published_ref drifted"):
        validate_state_slot_manifest(
            wrong_ref,
            model_id="P1",
            base_seed=1729,
            state_path=state_path,
        )
    sample_path = tmp_path / "reports/anfis_n_sample.csv"
    sample = pd.read_csv(sample_path, dtype={"site_id": "string"})
    sample.loc[0, "site_id"] = "000123"
    rank_payload = json.dumps(
        [
            int(sample.loc[0, "module_seed"]),
            str(sample.loc[0, "source_id"]),
            str(sample.loc[0, "site_id"]),
            str(sample.loc[0, "year_month"]),
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    sample.loc[0, "rank_sha256"] = hashlib.sha256(rank_payload).hexdigest()
    sample = sample.sort_values(
        ["rank_sha256", "source_id", "site_id", "year_month"],
        kind="mergesort",
    ).reset_index(drop=True)
    sample.to_csv(sample_path, index=False)
    payload["sampling"]["ANFIS-N"]["selected_keys_sha256"] = _sample_key_digest(sample)
    for output_record in payload["outputs"]:
        if output_record.get("role") == "sample_keys" and output_record.get("module") == "ANFIS-N":
            output_record.update(_file_record(sample_path))
    assert validate_state_slot_manifest(
        payload,
        model_id="P1",
        base_seed=1729,
        state_path=state_path,
    ) == (True, "", False)
    state_record = next(
        record
        for record in payload["outputs"]
        if isinstance(record, dict) and record.get("role") == "adaptive_no_current_state"
    )
    payload["outputs"] = [state_record]
    with pytest.raises(ValueError, match="anfis_checkpoint"):
        validate_state_slot_manifest(
            payload,
            model_id="P1",
            base_seed=1729,
            state_path=state_path,
        )
    payload["outputs"] = _anfis_outputs(
        tmp_path,
        state_path=state_path,
        dialect="available",
    )
    payload["base_seed"] = 20260612
    with pytest.raises(ValueError, match="base_seed"):
        validate_state_slot_manifest(
            payload,
            model_id="P1",
            base_seed=1729,
            state_path=state_path,
        )


def test_state_slot_manifest_accepts_only_closed_prefit_unavailable_dialect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_path = tmp_path / "state.parquet"
    payload: dict[str, Any] = {
        **_anfis_provenance(tmp_path, monkeypatch, state_path=state_path),
        **_anfis_scientific_fields(dialect="unavailable_not_attempted"),
        "manifest_version": "closure_anfis_seed_manifest_v1",
        "status": "completed",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": "F1",
        "consumer_model_id": "P1",
        "base_seed": 1729,
        "slot_status": "model_unavailable",
        "fit_status": "not_attempted",
        "failure_reason": "insufficient_eligible_training_rows",
        "state_artifact_emitted": False,
        "state_output_materialized": False,
        "checkpoint_outputs_materialized": False,
        "model_construction_attempted": False,
        "fit_attempted": False,
        "failed_slot_replaced": False,
        "replacement_used": False,
        "retain_failed_seed_slot": True,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "completion_marker_written_last": True,
        "outputs": _anfis_outputs(
            tmp_path,
            state_path=state_path,
            dialect="unavailable_not_attempted",
        ),
    }
    assert validate_state_slot_manifest(
        payload,
        model_id="P1",
        base_seed=1729,
        state_path=state_path,
    ) == (False, "insufficient_eligible_training_rows", False)
    typed_counts = copy.deepcopy(payload)
    typed_counts["counts"]["state_rows"] = False
    typed_counts["counts"]["unavailable_modules"] = True
    with pytest.raises(ValueError, match="counts/failed modules"):
        validate_state_slot_manifest(
            typed_counts,
            model_id="P1",
            base_seed=1729,
            state_path=state_path,
        )
    payload["state_artifact_emitted"] = True
    with pytest.raises(ValueError, match="state_artifact_emitted"):
        validate_state_slot_manifest(
            payload,
            model_id="P1",
            base_seed=1729,
            state_path=state_path,
        )


def test_state_slot_manifest_preserves_quality_gate_failure_cause(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_path = tmp_path / "state.parquet"
    payload: dict[str, Any] = {
        **_anfis_provenance(tmp_path, monkeypatch, state_path=state_path),
        **_anfis_scientific_fields(dialect="unavailable_failed"),
        "manifest_version": "closure_anfis_seed_manifest_v1",
        "status": "completed",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": "F1",
        "consumer_model_id": "P1",
        "base_seed": 1729,
        "slot_status": "model_unavailable",
        "fit_status": "failed",
        "failure_reason": "module_fit_quality_gate_failed",
        "state_artifact_emitted": True,
        "state_output_materialized": True,
        "checkpoint_outputs_materialized": True,
        "model_construction_attempted": True,
        "fit_attempted": True,
        "failed_slot_replaced": False,
        "replacement_used": False,
        "retain_failed_seed_slot": True,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "completion_marker_written_last": True,
        "outputs": _anfis_outputs(
            tmp_path,
            state_path=state_path,
            dialect="unavailable_failed",
        ),
    }
    assert validate_state_slot_manifest(
        payload,
        model_id="P1",
        base_seed=1729,
        state_path=state_path,
    ) == (False, "module_fit_quality_gate_failed", True)


def test_state_slot_manifest_rejects_stale_runtime_lock_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_path = tmp_path / "state.parquet"
    payload: dict[str, Any] = {
        **_anfis_provenance(tmp_path, monkeypatch, state_path=state_path),
        **_anfis_scientific_fields(dialect="available"),
        "manifest_version": "closure_anfis_seed_manifest_v1",
        "status": "completed",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": "F1",
        "consumer_model_id": "P1",
        "base_seed": 1729,
        "slot_status": "available",
        "fit_status": "passed",
        "failure_reason": "",
        "state_artifact_emitted": True,
        "state_output_materialized": True,
        "checkpoint_outputs_materialized": True,
        "model_construction_attempted": True,
        "fit_attempted": True,
        "failed_slot_replaced": False,
        "replacement_used": False,
        "retain_failed_seed_slot": False,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "completion_marker_written_last": True,
        "outputs": _anfis_outputs(tmp_path, state_path=state_path, dialect="available"),
    }
    typed_record_payload = copy.deepcopy(payload)
    for field in ("dependencies", "inputs"):
        for record in typed_record_payload[field]:
            if record.get("role") == "strict_expert_state_adapter":
                assert record["bytes"] == 1
                record["bytes"] = True
    with pytest.raises(ValueError, match="physical bytes"):
        validate_state_slot_manifest(
            typed_record_payload,
            model_id="P1",
            base_seed=1729,
            state_path=state_path,
        )
    wrong_path = tmp_path / "data/wrong_panel.parquet"
    wrong_path.write_bytes(b"wrong panel")
    wrong_record = {**_file_record(wrong_path), "role": "restored_panel"}
    wrong_payload = copy.deepcopy(payload)
    wrong_payload["dependencies"] = [
        wrong_record if record.get("role") == "restored_panel" else record
        for record in wrong_payload["dependencies"]
    ]
    wrong_payload["inputs"] = [
        wrong_record if record.get("role") == "restored_panel" else record
        for record in wrong_payload["inputs"]
    ]
    with pytest.raises(ValueError, match="role/path 'restored_panel'"):
        validate_state_slot_manifest(
            wrong_payload,
            model_id="P1",
            base_seed=1729,
            state_path=state_path,
        )
    (tmp_path / "reports/runtime_lock.json").write_bytes(b"new lock")
    with pytest.raises(ValueError, match="physical bytes"):
        validate_state_slot_manifest(
            payload,
            model_id="P1",
            base_seed=1729,
            state_path=state_path,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("substream", "module substreams"),
        ("sampling", "selected-row contract"),
        ("counts", "counts"),
        ("cpu", "CPU execution policy"),
        ("cpu_typed", "CPU execution policy"),
        ("authorization_extra", "authorization dialect"),
        ("join_scopes", "join scopes"),
        ("path_redirect", "paths/order"),
        ("sample_csv", "rank digest"),
        ("duplicate_sample_key", "keys are duplicated"),
        ("sample_seed_nonintegral", "sample CSV identity"),
        ("sample_scope", "string identity"),
        ("metrics_csv", "metrics CSV differs"),
        ("future_bool", "future_outcomes_accessed"),
        ("completion_bool", "completion_marker_written_last"),
        ("centers_bool", "metric 'ANFIS-N' drifted"),
        ("metric_dimension", "metric 'ANFIS-F' drifted"),
        ("sampling_conservation", "sampling conservation"),
        ("quality_status", "quality-gate status"),
        ("top_level", "top-level"),
        ("output_extra", "output record keys"),
    ],
)
def test_state_slot_manifest_rejects_scientific_dialect_mutations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    message: str,
) -> None:
    state_path = tmp_path / "state.parquet"
    payload: dict[str, Any] = {
        **_anfis_provenance(tmp_path, monkeypatch, state_path=state_path),
        **_anfis_scientific_fields(dialect="available"),
        "manifest_version": "closure_anfis_seed_manifest_v1",
        "status": "completed",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": "F1",
        "consumer_model_id": "P1",
        "base_seed": 1729,
        "slot_status": "available",
        "fit_status": "passed",
        "failure_reason": "",
        "state_artifact_emitted": True,
        "state_output_materialized": True,
        "checkpoint_outputs_materialized": True,
        "model_construction_attempted": True,
        "fit_attempted": True,
        "failed_slot_replaced": False,
        "replacement_used": False,
        "retain_failed_seed_slot": False,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "completion_marker_written_last": True,
        "outputs": _anfis_outputs(tmp_path, state_path=state_path, dialect="available"),
    }
    mutated = copy.deepcopy(payload)
    if mutation == "substream":
        mutated["module_substreams"]["ANFIS-N"] += 1
    elif mutation == "sampling":
        mutated["sampling"]["ANFIS-N"]["selected_rows"] = 4095
    elif mutation == "counts":
        mutated["counts"]["state_rows"] = 0
    elif mutation == "cpu":
        mutated["cpu_execution_policy"]["torch_num_threads_observed"] = 2
    elif mutation == "cpu_typed":
        mutated["cpu_execution_policy"]["torch_num_threads"] = 1.0
    elif mutation == "authorization_extra":
        mutated["authorization"]["unexpected"] = True
    elif mutation == "join_scopes":
        mutated["panel_anchor_joins"].pop("training_candidates")
    elif mutation == "path_redirect":
        redirected = tmp_path / "redirected/anfis_n.pt"
        redirected.parent.mkdir(parents=True)
        redirected.write_bytes(b"redirected")
        replacement = {
            **_file_record(redirected),
            "role": "anfis_checkpoint",
            "module": "ANFIS-N",
        }
        mutated["outputs"] = [
            replacement
            if record.get("role") == "anfis_checkpoint"
            and record.get("module") == "ANFIS-N"
            else record
            for record in mutated["outputs"]
        ]
    elif mutation == "sample_csv":
        sample_path = tmp_path / "reports/anfis_n_sample.csv"
        sample = pd.read_csv(sample_path)
        sample.loc[0, "rank_sha256"] = "f" * 64
        sample.to_csv(sample_path, index=False)
        for record in mutated["outputs"]:
            if record.get("role") == "sample_keys" and record.get("module") == "ANFIS-N":
                record.update(_file_record(sample_path))
    elif mutation == "duplicate_sample_key":
        sample_path = tmp_path / "reports/anfis_n_sample.csv"
        sample = pd.read_csv(sample_path, dtype={"source_id": "string", "site_id": "string"})
        for field in ("source_id", "site_id", "year_month"):
            sample.loc[1, field] = sample.loc[0, field]
        rank_payload = json.dumps(
            [
                int(sample.loc[1, "module_seed"]),
                str(sample.loc[1, "source_id"]),
                str(sample.loc[1, "site_id"]),
                str(sample.loc[1, "year_month"]),
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        sample.loc[1, "rank_sha256"] = hashlib.sha256(rank_payload).hexdigest()
        sample.to_csv(sample_path, index=False)
        for record in mutated["outputs"]:
            if record.get("role") == "sample_keys" and record.get("module") == "ANFIS-N":
                record.update(_file_record(sample_path))
    elif mutation == "sample_seed_nonintegral":
        sample_path = tmp_path / "reports/anfis_n_sample.csv"
        sample = pd.read_csv(sample_path, dtype=str)
        sample.loc[0, "module_seed"] = "1830.5"
        sample.to_csv(sample_path, index=False)
        for record in mutated["outputs"]:
            if record.get("role") == "sample_keys" and record.get("module") == "ANFIS-N":
                record.update(_file_record(sample_path))
    elif mutation == "sample_scope":
        sample_path = tmp_path / "reports/anfis_n_sample.csv"
        sample = pd.read_csv(sample_path, dtype=str)
        sample.loc[0, "source_id"] = " wqp"
        sample.to_csv(sample_path, index=False)
        for record in mutated["outputs"]:
            if record.get("role") == "sample_keys" and record.get("module") == "ANFIS-N":
                record.update(_file_record(sample_path))
    elif mutation == "metrics_csv":
        metrics_path = tmp_path / "reports/metrics.csv"
        metrics = pd.read_csv(metrics_path)
        metrics.loc[0, "train_rows"] = 4095
        metrics.to_csv(metrics_path, index=False)
        for record in mutated["outputs"]:
            if record.get("role") == "module_metrics":
                record.update(_file_record(metrics_path))
    elif mutation == "future_bool":
        mutated["future_outcomes_accessed"] = 0
    elif mutation == "completion_bool":
        mutated["completion_marker_written_last"] = 1
    elif mutation == "centers_bool":
        mutated["module_metrics"][0]["centers_ordered"] = 1
    elif mutation == "metric_dimension":
        mutated["module_metrics"][1]["input_dimension"] = 3
    elif mutation == "sampling_conservation":
        mutated["sampling"]["ANFIS-N"]["input_rows"] = 4999
    elif mutation == "quality_status":
        mutated["module_metrics"][0]["status"] = "failed"
    elif mutation == "top_level":
        mutated["unexpected"] = True
    else:
        mutated["outputs"][0]["unexpected"] = True
    with pytest.raises(ValueError, match=message):
        validate_state_slot_manifest(
            mutated,
            model_id="P1",
            base_seed=1729,
            state_path=state_path,
        )


def test_sequence_rejects_nonregistered_p1_seed_and_post_2021_geometry() -> None:
    with pytest.raises(ValueError, match="registered base seed"):
        build_closure_pipe_sequences(
            _state_frame(),
            _common_origin(),
            model_id="P1",
            base_seed=7,
            expected_origin_count=1,
        )

    common = _common_origin()
    common["origin_year_month"] = "2021-11"
    common["history_start_year_month"] = "2020-12"
    common["history_end_year_month"] = "2021-11"
    common["target_year_month"] = ["2021-12", "2022-01", "2022-02"]
    with pytest.raises(ValueError, match="beyond 2021-12"):
        build_closure_pipe_sequences(
            _state_frame(),
            common,
            model_id="P0",
            base_seed=None,
            expected_origin_count=1,
        )


def test_main_stops_at_external_gate_before_state_io(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    class GateStopped(RuntimeError):
        pass

    fake_lock = types.ModuleType(
        "src.experiments.closure_p1_sequence_seed_20260612_patch"
    )
    gate_calls: list[dict[str, object]] = []

    def stop_gate(**arguments: object) -> dict[str, object]:
        gate_calls.append(arguments)
        raise GateStopped

    setattr(
        fake_lock,
        "require_p1_sequence_seed_20260612_authorized",
        stop_gate,
    )
    monkeypatch.setitem(sys.modules, fake_lock.__name__, fake_lock)
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: Namespace(model_id="P1", base_seed=20260612),
    )
    io_calls: list[str] = []

    def unexpected_io(*_: object, **__: object) -> None:
        io_calls.append("unexpected")

    monkeypatch.setattr(module, "load_yaml_mapping", unexpected_io)
    monkeypatch.setattr(module, "load_development_gate", unexpected_io)
    monkeypatch.setattr(module, "_paths", unexpected_io)
    monkeypatch.setattr(module, "_sequence_bundle_guard", unexpected_io)
    monkeypatch.setattr(pd, "read_parquet", unexpected_io)

    with pytest.raises(GateStopped):
        module.main()
    assert gate_calls == [{"model_id": "P1", "base_seed": 20260612}]
    assert io_calls == []


def test_sequence_bundle_preflight_rejects_final_or_temporary_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    paths = {
        "sequence": Path("data/sequence.parquet"),
        "summary": Path("reports/summary.csv"),
        "manifest": Path("reports/manifest.json"),
    }
    assert_sequence_outputs_absent(paths)
    final = tmp_path / paths["summary"]
    final.parent.mkdir(parents=True)
    final.write_bytes(b"partial")
    with pytest.raises(ValueError, match="overwrite is forbidden"):
        assert_sequence_outputs_absent(paths)
    final.unlink()
    temporary = (tmp_path / paths["sequence"]).with_suffix(".parquet.tmp")
    temporary.parent.mkdir(parents=True)
    temporary.write_bytes(b"interrupted")
    with pytest.raises(ValueError, match="overwrite is forbidden"):
        assert_sequence_outputs_absent(paths)
    temporary.unlink()
    pointer = Path(f"{(tmp_path / paths['sequence']).as_posix()}.dvc")
    pointer.write_bytes(b"outs: []")
    with pytest.raises(ValueError, match="overwrite is forbidden"):
        assert_sequence_outputs_absent(paths)
    with pytest.raises(ValueError, match="Concurrent DVC registration"):
        module.assert_sequence_pointer_absent(paths)
    pointer.unlink()
    for candidate in (final, temporary, pointer):
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.symlink_to(tmp_path / "missing-target")
        with pytest.raises(ValueError, match="overwrite is forbidden"):
            assert_sequence_outputs_absent(paths)
        candidate.unlink()


def test_sequence_bundle_guard_is_exclusive_for_the_full_slot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    with module._sequence_bundle_guard("P0", None):
        with pytest.raises(ValueError, match="already reserved"):
            with module._sequence_bundle_guard("P0", None):
                raise AssertionError("unreachable")
        assert (tmp_path / "tmp/closure_v1_sequence_builder/P0.guard").is_file()
    assert not (tmp_path / "tmp/closure_v1_sequence_builder/P0.guard").exists()


def test_sequence_bundle_transaction_rolls_back_prior_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    first = tmp_path / "data/sequence.parquet"
    second = tmp_path / "reports/summary.csv"

    def fail_writer(handle: Any) -> None:
        handle.write("partial")
        raise RuntimeError("summary failed")

    with pytest.raises(RuntimeError, match="summary failed"):
        with module._SequenceOutputTransaction() as transaction:
            transaction._publish(
                first,
                lambda handle: handle.write(b"sequence"),
                binary=True,
            )
            transaction._publish(second, fail_writer, binary=False)

    assert not first.exists()
    assert not second.exists()
    assert not first.with_suffix(".parquet.tmp").exists()
    assert not second.with_suffix(".csv.tmp").exists()


def test_sequence_bundle_transaction_rolls_back_parquet_and_summary_if_manifest_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    sequence = tmp_path / "data/sequence.parquet"
    summary = tmp_path / "reports/summary.csv"
    manifest = tmp_path / "reports/manifest.json"

    def fail_manifest(handle: Any) -> None:
        handle.write("{")
        raise RuntimeError("manifest failed")

    with pytest.raises(RuntimeError, match="manifest failed"):
        with module._SequenceOutputTransaction() as transaction:
            transaction._publish(
                sequence,
                lambda handle: handle.write(b"sequence"),
                binary=True,
            )
            transaction._publish(
                summary,
                lambda handle: handle.write("summary"),
                binary=False,
            )
            transaction._publish(manifest, fail_manifest, binary=False)

    assert all(not path.exists() for path in (sequence, summary, manifest))


def test_sequence_bundle_transaction_preserves_a_foreign_final_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    first = tmp_path / "data/sequence.parquet"
    second = tmp_path / "reports/summary.csv"

    with pytest.raises(ValueError, match="identity drifted"):
        with module._SequenceOutputTransaction() as transaction:
            transaction._publish(
                first,
                lambda handle: handle.write(b"owned-sequence"),
                binary=True,
            )
            transaction._publish(
                second,
                lambda handle: handle.write("owned-summary"),
                binary=False,
            )
            first.unlink()
            first.write_bytes(b"foreign replacement")

    assert first.read_bytes() == b"foreign replacement"
    assert not second.exists()


def test_sequence_bundle_transaction_rolls_back_if_guard_release_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    output = tmp_path / "reports/manifest.json"
    original_unlink = module._unlink_name_if_owned

    def fail_guard_release(
        descriptor: int,
        name: str,
        *,
        device: int,
        inode: int,
    ) -> bool:
        if name == "P1_seed_1729.guard":
            raise OSError("guard release failed")
        return original_unlink(
            descriptor,
            name,
            device=device,
            inode=inode,
        )

    monkeypatch.setattr(module, "_unlink_name_if_owned", fail_guard_release)
    with pytest.raises(ValueError, match="guard cleanup"):
        with module._SequenceOutputTransaction() as transaction:
            with module._sequence_bundle_guard("P1", 1729):
                transaction.publish_json({"completed": True}, output)

    assert not output.exists()


def test_concurrent_dvc_pointer_rolls_back_bundle_but_is_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    paths = {
        "sequence": Path("data/sequence.parquet"),
        "summary": Path("reports/summary.csv"),
        "manifest": Path("reports/manifest.json"),
    }
    sequence = tmp_path / paths["sequence"]
    summary = tmp_path / paths["summary"]
    pointer = Path(f"{sequence.as_posix()}.dvc")

    with pytest.raises(ValueError, match="Concurrent DVC registration"):
        with module._SequenceOutputTransaction() as transaction:
            with module._sequence_bundle_guard("P1", 1729):
                transaction._publish(
                    sequence,
                    lambda handle: handle.write(b"sequence"),
                    binary=True,
                )
                transaction._publish(
                    summary,
                    lambda handle: handle.write("summary"),
                    binary=False,
                )
                pointer.write_bytes(b"outs: []\n")
                module.assert_sequence_pointer_absent(paths)

    assert not sequence.exists()
    assert not summary.exists()
    assert pointer.read_bytes() == b"outs: []\n"


def test_sequence_writer_preserves_a_foreign_temp_replacement_after_hardlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    output = tmp_path / "reports/summary.json"
    temporary = output.with_suffix(".json.tmp")
    original_link = os.link

    def replace_after_link(*args: Any, **kwargs: Any) -> None:
        original_link(*args, **kwargs)
        temporary.unlink()
        temporary.write_bytes(b"foreign temp replacement\n")

    monkeypatch.setattr(os, "link", replace_after_link)
    with pytest.raises(ValueError, match="Temporary artifact changed before cleanup"):
        module._write_json_atomic({"ours": True}, output)
    assert temporary.read_bytes() == b"foreign temp replacement\n"
    assert not output.exists()


def test_sequence_guard_rejects_a_symlinked_coordination_ancestor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    repository = tmp_path / "repository"
    outside = tmp_path / "outside"
    repository.mkdir()
    outside.mkdir()
    (repository / "tmp").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(module, "PROJECT_ROOT", repository)
    with pytest.raises(ValueError, match="ancestor is not a real directory"):
        with module._sequence_bundle_guard("P1", 1729):
            raise AssertionError("unreachable")
    assert list(outside.iterdir()) == []


def test_sequence_writer_never_clobbers_final_or_broken_temporary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    output = tmp_path / "reports/summary.json"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"racing writer\n")
    with pytest.raises(ValueError, match="overwrite final artifact"):
        module._write_json_atomic({"ours": True}, output)
    assert output.read_bytes() == b"racing writer\n"
    assert not output.with_suffix(output.suffix + ".tmp").exists()

    output.unlink()
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.symlink_to(tmp_path / "missing-target")
    with pytest.raises(ValueError, match="overwrite temporary artifact"):
        module._write_json_atomic({"ours": True}, output)
    assert temporary.is_symlink()
    assert not output.exists()
    temporary.unlink()

    def replace_temporary(handle: Any) -> None:
        handle.write(b"owned\n")
        temporary.unlink()
        temporary.write_bytes(b"foreign replacement\n")

    with pytest.raises(ValueError, match="identity drifted"):
        module._write_output_no_clobber(output, replace_temporary, binary=True)
    assert temporary.read_bytes() == b"foreign replacement\n"
    assert not output.exists()
    temporary.unlink()

    original_fsync = os.fsync
    fsync_calls = 0

    def fail_directory_fsync(descriptor: int) -> None:
        nonlocal fsync_calls
        fsync_calls += 1
        if fsync_calls == 2:
            raise OSError("directory fsync failed")
        original_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", fail_directory_fsync)
    with pytest.raises(OSError, match="directory fsync failed"):
        module._write_output_no_clobber(
            output,
            lambda handle: handle.write(b"owned\n"),
            binary=True,
        )
    assert not output.exists()
    assert not temporary.exists()


def test_sequence_writer_rejects_a_symlinked_output_ancestor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    repository = tmp_path / "repository"
    outside = tmp_path / "outside"
    repository.mkdir()
    outside.mkdir()
    (repository / "reports").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(module, "PROJECT_ROOT", repository)
    output = repository / "reports/summary.json"
    with pytest.raises(ValueError, match="ancestor is not a real directory"):
        module._write_json_atomic({"ours": True}, output)
    assert list(outside.iterdir()) == []


def test_sequence_transaction_rehashes_and_rolls_back_same_inode_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    sequence = tmp_path / "data/sequence.parquet"
    summary = tmp_path / "reports/summary.csv"

    with pytest.raises(ValueError, match="bytes drifted before commit"):
        with module._SequenceOutputTransaction() as transaction:
            transaction._publish(
                sequence,
                lambda handle: handle.write(b"original-sequence"),
                binary=True,
            )
            transaction._publish(
                summary,
                lambda handle: handle.write("original-summary"),
                binary=False,
            )
            original_inode = sequence.stat().st_ino
            sequence.write_bytes(b"mutated-sequence!")
            assert sequence.stat().st_ino == original_inode

    assert not sequence.exists()
    assert not summary.exists()


def test_sequence_transaction_rechecks_dvc_pointer_at_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    sequence = tmp_path / "data/sequence.parquet"
    summary = tmp_path / "reports/summary.csv"
    pointer = Path(f"{sequence.as_posix()}.dvc")

    with pytest.raises(ValueError, match="forbidden sequence artifact"):
        with module._SequenceOutputTransaction() as transaction:
            transaction.forbid_path_entries((pointer,))
            transaction._publish(
                sequence,
                lambda handle: handle.write(b"sequence"),
                binary=True,
            )
            transaction._publish(
                summary,
                lambda handle: handle.write("summary"),
                binary=False,
            )
            pointer.write_bytes(b"outs: []\n")

    assert not sequence.exists()
    assert not summary.exists()
    assert pointer.read_bytes() == b"outs: []\n"


def test_sequence_transaction_rechecks_pointer_after_output_rehash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    sequence = tmp_path / "data/sequence.parquet"
    summary = tmp_path / "reports/summary.csv"
    pointer = Path(f"{sequence.as_posix()}.dvc")
    original_record = module._owned_sequence_file_record
    injected = False

    def record_then_register(
        owned: Any,
    ) -> dict[str, Any]:
        nonlocal injected
        record = original_record(owned)
        if not injected:
            pointer.write_bytes(b"outs: []\n")
            injected = True
        return record

    monkeypatch.setattr(module, "_owned_sequence_file_record", record_then_register)
    with pytest.raises(ValueError, match="appeared during commit"):
        with module._SequenceOutputTransaction() as transaction:
            transaction.forbid_path_entries((pointer,))
            transaction._publish(
                sequence,
                lambda handle: handle.write(b"sequence"),
                binary=True,
            )
            transaction._publish(
                summary,
                lambda handle: handle.write("summary"),
                binary=False,
            )

    assert not sequence.exists()
    assert not summary.exists()
    assert pointer.read_bytes() == b"outs: []\n"


def test_sequence_transaction_revalidates_dependencies_after_serialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    dependency = tmp_path / "reports/authority.json"
    dependency.parent.mkdir(parents=True)
    dependency.write_bytes(b"sealed-authority\n")
    expected = module._file_record(dependency)
    output = tmp_path / "data/sequence.parquet"

    def validate_dependency() -> None:
        if module._file_record(dependency) != expected:
            raise module.ClosurePipeSequenceError(
                "A sequence dependency changed during construction"
            )

    with pytest.raises(ValueError, match="dependency changed"):
        with module._SequenceOutputTransaction() as transaction:
            transaction.add_commit_validator(validate_dependency)
            transaction._publish(
                output,
                lambda handle: handle.write(b"sequence"),
                binary=True,
            )
            dependency.write_bytes(b"changed-authority\n")

    assert not output.exists()


def test_output_parent_walk_closes_child_when_fstat_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    repository = tmp_path / "repository"
    (repository / "reports").mkdir(parents=True)
    monkeypatch.setattr(module, "PROJECT_ROOT", repository)
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
        if len(opened) >= 2 and descriptor == opened[1]:
            raise OSError("injected child fstat failure")
        return real_fstat(descriptor)

    def tracked_close(descriptor: int) -> None:
        closed.append(descriptor)
        real_close(descriptor)

    monkeypatch.setattr(os, "open", tracked_open)
    monkeypatch.setattr(os, "fstat", fail_child_fstat)
    monkeypatch.setattr(os, "close", tracked_close)
    with pytest.raises(OSError, match="child fstat failure"):
        module._open_real_output_parent(repository / "reports/output.json")

    assert len(opened) == 2
    assert sorted(closed) == sorted(opened)


def test_authorization_inputs_are_exact_and_use_generic_manifest_record_dialect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    roles = {
        "reports/closure_v1/00_protocol/"
        "p1_sequence_seed_20260612_patch_lock.json": (
            "external_p1_sequence_seed_20260612_patch_lock"
        ),
        "reports/closure_v1/00_protocol/"
        "p1_sequence_seed_20260612_patch_lock_manifest.json": (
            "p1_sequence_seed_20260612_patch_companion"
        ),
    }
    inputs: list[dict[str, Any]] = []
    for index, (path, role) in enumerate(roles.items(), start=1):
        physical = tmp_path / path
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_bytes(f"authority-{index}\n".encode())
        inputs.append({**module._file_record(physical), "role": role})

    dependencies = module._authorization_dependency_records(
        {"authorization_inputs": inputs}
    )
    assert {record["path"] for record in dependencies} == set(roles)
    assert all(set(record) == {"path", "bytes", "sha256"} for record in dependencies)

    inputs[0]["role"] = "wrong_role"
    with pytest.raises(ValueError, match="paths or roles drifted"):
        module._authorization_dependency_records({"authorization_inputs": inputs})


def test_sequence_transaction_rolls_back_if_e0_mh_authority_mutates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    roles = {
        "reports/closure_v1/00_protocol/"
        "p1_sequence_seed_20260612_patch_lock.json": (
            "external_p1_sequence_seed_20260612_patch_lock"
        ),
        "reports/closure_v1/00_protocol/"
        "p1_sequence_seed_20260612_patch_lock_manifest.json": (
            "p1_sequence_seed_20260612_patch_companion"
        ),
    }
    inputs: list[dict[str, Any]] = []
    for index, (path, role) in enumerate(roles.items(), start=1):
        physical = tmp_path / path
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_bytes(f"authority-{index}\n".encode())
        inputs.append({**module._file_record(physical), "role": role})
    dependencies = module._authorization_dependency_records(
        {"authorization_inputs": inputs}
    )

    def validate_authority_dependencies() -> None:
        observed = [
            module._file_record(tmp_path / str(record["path"]))
            for record in dependencies
        ]
        if observed != dependencies:
            raise module.ClosurePipeSequenceError(
                "A sequence dependency changed during construction"
            )

    sequence = tmp_path / "data/sequence.parquet"
    summary = tmp_path / "reports/summary.csv"
    companion = tmp_path / next(
        path for path, role in roles.items() if role.endswith("_companion")
    )
    with pytest.raises(ValueError, match="dependency changed"):
        with module._SequenceOutputTransaction() as transaction:
            transaction.add_commit_validator(validate_authority_dependencies)
            transaction._publish(
                sequence,
                lambda handle: handle.write(b"sequence"),
                binary=True,
            )
            transaction._publish(
                summary,
                lambda handle: handle.write("summary"),
                binary=False,
            )
            companion.write_bytes(b"mutated companion\n")

    assert not sequence.exists()
    assert not summary.exists()
    assert companion.read_bytes() == b"mutated companion\n"


def test_sequence_manifest_reuses_one_frozen_builder_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.experiments import build_closure_pipe_sequences as module

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    builder = tmp_path / "src/experiments/build_closure_pipe_sequences.py"
    builder.parent.mkdir(parents=True)
    builder.write_bytes(b"frozen builder\n")
    monkeypatch.setattr(module, "__file__", builder.as_posix())
    record = module._file_record(builder)
    binding = module._sequence_builder_manifest_binding(record)
    assert binding == {"script": record, "source_code": [record]}
    assert binding["script"] is not binding["source_code"][0]

    corrupted = dict(record)
    corrupted["path"] = "src/experiments/other.py"
    with pytest.raises(ValueError, match="Frozen sequence-builder record drifted"):
        module._sequence_builder_manifest_binding(corrupted)
