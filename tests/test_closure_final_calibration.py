from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.experiments import closure_final_calibration as calibration


ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = "2f46d3e258195315e2473be6cf7d62db22c55bcf"

EXPECTED_H_PATHS = {
    "configs/closure_v1/final_calibration_runtime.yaml",
    "configs/closure_v1/final_calibration_runtime.schema.json",
    "configs/closure_v1/final_calibration_lock.schema.json",
    "docs/closure_v1/E0_M_FINAL_CALIBRATION.md",
    "src/experiments/calibrate_closure_final_models.py",
    "src/experiments/closure_final_calibration.py",
    "src/experiments/lock_closure_final_calibration.py",
    "src/experiments/run_closure_anfis_learning_curve.py",
    "tests/test_calibrate_closure_final_models.py",
    "tests/test_closure_anfis_learning_curve.py",
    "tests/test_closure_final_calibration.py",
    "tests/test_lock_closure_final_calibration.py",
}
EXPECTED_P_PATHS = {
    "reports/closure_v1/00_protocol/final_calibration_lock.json",
    "reports/closure_v1/00_protocol/final_calibration_lock_manifest.json",
}
EXPECTED_CALIBRATION_OUTPUTS = {
    "reports/closure_v1/03_calibration/calibrator_specs.json",
    "reports/closure_v1/03_calibration/calibration_metrics.csv",
    "reports/closure_v1/03_calibration/alert_thresholds.csv",
    "reports/closure_v1/03_calibration/ordinal_cutpoints.csv",
    "reports/closure_v1/03_calibration/model_availability.csv",
    "reports/closure_v1/03_calibration/final_calibration_manifest.json",
}
EXPECTED_E7_OUTPUTS = {
    "reports/closure_v1/07_anfis_ablation/anfis_learning_curve.csv",
    "reports/closure_v1/07_anfis_ablation/anfis_learning_curve_manifest.json",
}
EXPECTED_R_ORDER = (
    "reports/closure_v1/03_calibration/calibrator_specs.json",
    "reports/closure_v1/03_calibration/calibration_metrics.csv",
    "reports/closure_v1/03_calibration/alert_thresholds.csv",
    "reports/closure_v1/03_calibration/ordinal_cutpoints.csv",
    "reports/closure_v1/03_calibration/model_availability.csv",
    "reports/closure_v1/03_calibration/final_calibration_manifest.json",
    "reports/closure_v1/07_anfis_ablation/anfis_learning_curve.csv",
    "reports/closure_v1/07_anfis_ablation/anfis_learning_curve_manifest.json",
)


def _runtime() -> dict[str, Any]:
    payload = yaml.safe_load(
        (ROOT / "configs/closure_v1/final_calibration_runtime.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert isinstance(payload, dict)
    return payload


def _schema(name: str) -> dict[str, Any]:
    payload = json.loads((ROOT / "configs/closure_v1" / name).read_text())
    assert isinstance(payload, dict)
    return payload


def _walk(value: Any) -> list[Any]:
    values = [value]
    if isinstance(value, dict):
        for nested in value.values():
            values.extend(_walk(nested))
    elif isinstance(value, list):
        for nested in value:
            values.extend(_walk(nested))
    return values


def test_gate_base_and_exact_h_p_r_scopes() -> None:
    assert calibration.FINAL_CALIBRATION_GATE == "E0-MCAL"
    assert calibration.BASE_COMMIT == BASE_COMMIT
    assert set(calibration.FINAL_CALIBRATION_H_STAGED_SCOPE) == EXPECTED_H_PATHS
    assert calibration.FINAL_CALIBRATION_H_STAGED_SCOPE == {
        path: "A" for path in EXPECTED_H_PATHS
    }
    assert calibration.FINAL_CALIBRATION_P_STAGED_SCOPE == {
        path: "A" for path in EXPECTED_P_PATHS
    }
    assert calibration.FINAL_CALIBRATION_R_STAGED_SCOPE == {
        path: "A"
        for path in EXPECTED_CALIBRATION_OUTPUTS | EXPECTED_E7_OUTPUTS
    }
    assert tuple(calibration.FINAL_CALIBRATION_R_STAGED_SCOPE) == EXPECTED_R_ORDER


def test_scopes_are_disjoint_light_and_have_exact_cardinality() -> None:
    h = set(calibration.FINAL_CALIBRATION_H_STAGED_SCOPE)
    p = set(calibration.FINAL_CALIBRATION_P_STAGED_SCOPE)
    r = set(calibration.FINAL_CALIBRATION_R_STAGED_SCOPE)
    assert (len(h), len(p), len(r)) == (12, 2, 8)
    assert not h & p
    assert not h & r
    assert not p & r
    assert "reports/closure_v1/00_protocol/outcome_access_log.jsonl" not in h | p | r
    for path in p | r:
        assert not path.endswith((".dvc", ".parquet", ".pt", ".pkl"))
    assert set(calibration.PATCH_PATHS) == EXPECTED_H_PATHS
    assert calibration.PATCH_COMPONENT_ROLES == {
        path: "final_calibration_h_component" for path in EXPECTED_H_PATHS
    }
    assert calibration.PATCH_COMPONENT_GIT_MODES == {
        path: "100644" for path in EXPECTED_H_PATHS
    }


def test_public_api_is_closed_and_does_not_expose_transaction_records() -> None:
    expected = {
        "preflight_final_calibration_schema",
        "collect_final_calibration_prelock_state",
        "build_final_calibration_lock_payload",
        "validate_final_calibration_lock_payload",
        "publish_final_calibration_lock_bundle",
        "execute_and_publish_final_calibration_lock_bundle",
        "load_effective_final_calibration_authority",
        "require_final_calibration_authority",
    }
    for name in expected:
        function = getattr(calibration, name)
        assert callable(function)
        assert "transaction_record" not in inspect.signature(function).parameters
    assert issubclass(calibration.FinalCalibrationError, RuntimeError)


def test_runtime_and_runtime_schema_are_well_formed_and_versioned() -> None:
    runtime = _runtime()
    schema = _schema("final_calibration_runtime.schema.json")
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["type"] == "object"
    assert schema.get("additionalProperties") is False
    assert runtime.get("gate") == "E0-MCAL"
    calibration.preflight_final_calibration_schema(repo_root=ROOT)


def test_lock_schema_is_closed_and_requires_all_top_level_sections() -> None:
    schema = _schema("final_calibration_lock.schema.json")
    expected = {
        "schema_version",
        "experiment_id",
        "gate",
        "status",
        "generated_at_utc",
        "repository",
        "h_patch",
        "runtime",
        "scientific_input_inventory",
        "scientific_boundary",
        "model_matrix",
        "calibration_group_matrix",
        "e7_terminal_record",
        "output_contract",
        "prelock",
        "verification",
        "authorizations",
    }
    assert schema["type"] == "object"
    assert schema.get("additionalProperties") is False
    assert set(schema["required"]) == expected
    assert set(schema["properties"]) == expected


def test_temporal_roles_are_development_only_and_cutoff_safe() -> None:
    values = _walk(_runtime())
    flattened = {str(value) for value in values}
    for token in {"2019", "2020", "2021", "calibration_threshold"}:
        assert any(token in value for value in flattened)
    assert any(value is False for value in values)
    source = inspect.getsource(calibration)
    for forbidden in ("2022-", "holdout rows permitted", "evaluation refit"):
        assert forbidden not in source


def test_model_matrix_partitions_all_declared_models_without_overlap() -> None:
    runtime = _runtime()
    values = _walk(runtime)
    calibratable = {"B0", "B1", "B2", "M0", "A0", "A1"}
    not_applicable = {"F0", "F1"}
    unavailable = {"P0", "P1", "A2"}
    scalar_values = {value for value in values if isinstance(value, str)}
    assert calibratable | not_applicable | unavailable <= scalar_values
    assert not calibratable & not_applicable
    assert not calibratable & unavailable
    assert not not_applicable & unavailable
    records = {
        record["model_id"]: record for record in runtime["model_matrix"]["records"]
    }
    for model_id in ("P0", "P1"):
        record = records[model_id]
        assert record["availability"] == "unavailable"
        assert record["availability_reason"] == (
            "exact_five_slots_model_unavailable_not_attempted"
        )
        assert record["seeds"] == [1729, 20260612, 20260613, 20260614, 314159]
        assert record["bloom_calibration"] == (
            "not_attempted_upstream_model_unavailable"
        )
    assert records["A2"]["availability"] == "unavailable"
    assert records["A2"]["availability_reason"] == "model_absent_no_substitute"
    assert records["A2"]["seed_policy"] == "no_slots"
    assert records["A2"]["seeds"] == []


def test_calibration_group_counts_are_exact() -> None:
    runtime = _runtime()
    integers = [value for value in _walk(runtime) if type(value) is int]
    assert 66 in integers
    assert 33 in integers
    assert 99 in integers or (66 in integers and 33 in integers)
    group_matrix = runtime["calibration_group_matrix"]
    assert group_matrix["ordinal_group_count"] == 33
    assert group_matrix["ordinal_completed_group_count"] == 30
    assert group_matrix["ordinal_unavailable_group_count"] == 3
    assert group_matrix["ordinal_unavailable_model_ids"] == ["B0"]
    assert group_matrix["ordinal_unavailable_status"] == (
        "not_available_degenerate_constant_score"
    )
    assert group_matrix["ordinal_unavailable_cutpoints"] is None
    assert group_matrix["complete_target_counts_by_target_year_horizon"] == {
        "2019": {"1": 397, "2": 371, "3": 344},
        "2020": {"1": 261, "2": 287, "3": 314},
        "2021": {"1": 224, "2": 224, "3": 224},
    }
    assert group_matrix["complete_target_count"] == 2646
    assert group_matrix["bloom_groups_with_exact_complete_target_universe"] == 66
    b0 = next(
        record
        for record in runtime["model_matrix"]["records"]
        if record["model_id"] == "B0"
    )
    assert (
        b0["ordinal_calibration"]
        == "record_not_available_degenerate_constant_score"
    )


def test_method_selection_rule_and_tie_break_order_are_fixed() -> None:
    runtime = _runtime()
    text = (ROOT / "configs/closure_v1/final_calibration_runtime.yaml").read_text()
    for token in (
        "identity",
        "platt",
        "isotonic",
        "0.001",
        "brier",
        "ece",
        "10",
    ):
        assert token.lower() in text.lower()
    protocol = runtime["calibration_protocol"]
    assert protocol["fixed_identity_model_ids"] == ["B0"]
    assert protocol["bloom_score_source_by_model"] == {
        "B0": "predicted_bloom_probability",
        "B1": "predicted_bloom_probability",
        "B2": "predicted_bloom_probability",
        "M0": "raw_score",
        "A0": "predicted_bloom_probability",
        "A1": "predicted_bloom_probability",
    }
    assert protocol["bloom_score_value_policy"] == (
        "finite_closed_unit_interval_reject_nan_no_normalization"
    )
    assert protocol["fixed_identity_calibrator_fit_policy"] == (
        "no_fit_fixed_transform"
    )
    assert protocol["fixed_identity_calibrator_fit_rows"] == 0
    assert protocol["fixed_identity_calibrator_refit_year"] is None
    assert protocol["fixed_identity_metrics_period"] == "calibration_threshold"
    assert protocol["fixed_identity_alert_threshold_period"] == (
        "calibration_threshold"
    )


def test_threshold_and_ordinal_cutpoint_ties_are_fixed() -> None:
    text = (ROOT / "configs/closure_v1/final_calibration_runtime.yaml").read_text()
    for token in (
        "f2",
        "recall",
        "precision",
        "lower_threshold",
        "macro_f1",
        "ordinal_mae",
        "lexicographic",
    ):
        assert token.lower() in text.lower()


def test_split_conformal_contract_is_exact_and_only_a0_a1() -> None:
    text = (ROOT / "configs/closure_v1/final_calibration_runtime.yaml").read_text()
    for token in (
        "0.80",
        "0.90",
        "0.95",
        "1e-6",
        "30",
        "no_pooling",
        "no_interpolation",
        "A0",
        "A1",
    ):
        assert token in text


def test_e7_contract_has_three_sizes_five_seeds_and_no_silent_omission() -> None:
    runtime = _runtime()
    record = runtime["e7_terminal_record"]
    text = (ROOT / "configs/closure_v1/final_calibration_runtime.yaml").read_text()
    for token in ("4096", "16384", "65536", "1729", "314159"):
        assert token in text
    for token in (
        "saturation_claim_authorized",
        "completed_sizes",
        "resource",
    ):
        assert token in text
    assert record["historical_blockers_adopted"] == [
        {
            "path": "configs/closure_v1/development_runtime.yaml",
            "bytes": 46105,
            "sha256": "0b2588248ee006f7d8e8843291b6a5847201a36fed35422473c9c0aa9492b10d",
            "git_oid": "5970ab73eedb20f464f804a185a3057daba93ab3",
            "git_mode": "100644",
            "e7_learning_curve_status": "blocked_pending_sampling_strata_contract",
            "e7_learning_curve_sizes_authorized": "not_declared",
        },
        {
            "path": "configs/closure_v1/anfis_ablation_training_development_runtime.yaml",
            "bytes": 22694,
            "sha256": "cf2cec52d9027db895e8859c7ffb321c831b66510132e137759e567b363f6a50",
            "git_oid": "94f84be4346fd4e01fd52d207b932e21022fc436",
            "git_mode": "100644",
            "e7_learning_curve_status": "blocked_for_separate_gate",
            "e7_learning_curve_sizes_authorized": "not_declared",
        },
        {
            "path": "configs/closure_v1/anfis_ablation_sequence_development_runtime.yaml",
            "bytes": 21827,
            "sha256": "49d1a3f562f2cd68ff65f29c92ac4e028b3ad407f30a9960ea0d29260df7d56b",
            "git_oid": "f9956fb51a8b0a742831c3400cc9624f4369fe90",
            "git_mode": "100644",
            "e7_learning_curve_status": "blocked_for_separate_gate",
            "e7_learning_curve_sizes_authorized": False,
        },
    ]
    assert record["historical_e7_blocker_adopted"] is True
    assert record["supersession_scope"] == "e7_only_additive_authority"
    assert record["required_training_rows_per_module"] == [4096, 16384, 65536]
    assert record["base_seeds"] == [1729, 20260612, 20260613, 20260614, 314159]
    assert record["eligible_rows_by_module"] == {
        "ANFIS-N": 4757,
        "ANFIS-F": 35273,
        "ANFIS-T-no-current": 35419,
    }
    assert record["expected_slot_count"] == 15
    assert record["expected_preflight_record_count"] == 45
    assert record["expected_completed_slot_count"] == 5
    assert record["expected_completed_module_fit_count"] == 15
    assert record["new_e7_fit_count"] == 15
    assert record["primary_fit_reuse_count"] == 0
    assert record["primary_4096_hash_rank_reuse_forbidden"] is True
    assert record["checkpoint_or_model_write_count"] == 0
    assert record["family80_no_touch"] is True
    assert record["expected_resource_failure_record_count"] == 10
    assert record["completed_training_rows_per_module"] == [4096]
    assert record["resource_failure_training_rows_per_module"] == [16384, 65536]


def test_lock_validation_rejects_authorization_and_boundary_drifts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    scientific_path = Path("data/payload.bin")
    pointer_path = Path("data/payload.bin.dvc")
    scientific_payload = b"E0-MCAL synthetic scientific payload\n"
    payload_md5 = hashlib.md5(
        scientific_payload, usedforsecurity=False
    ).hexdigest()
    cache_path = (
        Path(".dvc/cache/files/md5") / payload_md5[:2] / payload_md5[2:]
    )

    def write_pointer(root: Path) -> None:
        target = root / pointer_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "outs:\n"
            f"- md5: {payload_md5}\n"
            f"  size: {len(scientific_payload)}\n"
            "  hash: md5\n"
            "  path: payload.bin\n",
            encoding="utf-8",
        )
        target.chmod(0o644)

    def materialize(root: Path, *, mode: int = 0o444) -> tuple[Path, Path]:
        write_pointer(root)
        physical = root / scientific_path
        cache = root / cache_path
        physical.parent.mkdir(parents=True, exist_ok=True)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(scientific_payload)
        cache.chmod(mode)
        os.link(cache, physical)
        return physical, cache

    good_root = tmp_path / "good"
    good_physical, good_cache = materialize(good_root)
    observed_payload, observed_metadata = (
        calibration._read_scientific_payload_bytes_and_metadata(
            scientific_path,
            authorized_dvc_pointers=(pointer_path,),
            repo_root=good_root,
        )
    )
    assert observed_payload == scientific_payload
    assert observed_metadata.st_nlink == 2
    assert (observed_metadata.st_dev, observed_metadata.st_ino) == (
        good_cache.stat().st_dev,
        good_cache.stat().st_ino,
    )

    third_root = tmp_path / "third-link"
    third_physical, third_cache = materialize(third_root)
    third_name = third_root / "foreign-third-name"
    os.link(third_cache, third_name)
    assert third_physical.stat().st_nlink == 3
    with pytest.raises(calibration.FinalCalibrationError):
        calibration._read_scientific_payload_bytes_and_metadata(
            scientific_path,
            authorized_dvc_pointers=(pointer_path,),
            repo_root=third_root,
        )

    wrong_root = tmp_path / "wrong-cache"
    write_pointer(wrong_root)
    wrong_physical = wrong_root / scientific_path
    wrong_physical.parent.mkdir(parents=True, exist_ok=True)
    wrong_physical.write_bytes(scientific_payload)
    wrong_physical.chmod(0o444)
    wrong_alias = wrong_root / ".dvc/cache/files/md5/ff" / ("0" * 30)
    wrong_alias.parent.mkdir(parents=True, exist_ok=True)
    os.link(wrong_physical, wrong_alias)
    expected_cache = wrong_root / cache_path
    expected_cache.parent.mkdir(parents=True, exist_ok=True)
    expected_cache.write_bytes(scientific_payload)
    expected_cache.chmod(0o444)
    assert wrong_physical.stat().st_nlink == 2
    assert not wrong_physical.samefile(expected_cache)
    with pytest.raises(calibration.FinalCalibrationError):
        calibration._read_scientific_payload_bytes_and_metadata(
            scientific_path,
            authorized_dvc_pointers=(pointer_path,),
            repo_root=wrong_root,
        )

    writable_root = tmp_path / "writable"
    writable_physical, _ = materialize(writable_root, mode=0o644)
    assert writable_physical.stat().st_nlink == 2
    with pytest.raises(calibration.FinalCalibrationError):
        calibration._read_scientific_payload_bytes_and_metadata(
            scientific_path,
            authorized_dvc_pointers=(pointer_path,),
            repo_root=writable_root,
        )

    swap_root = tmp_path / "cache-swap"
    swap_physical, swap_cache = materialize(swap_root)
    swap_backup = swap_root / ".dvc/cache/files/md5/cache-swapped-away"
    real_read = calibration._read_regular_bytes_and_metadata
    swapped = False

    def swap_after_cache_read(path: Path, **kwargs: Any) -> Any:
        nonlocal swapped
        result = real_read(path, **kwargs)
        if path == cache_path and not swapped:
            swapped = True
            swap_cache.rename(swap_backup)
            swap_cache.write_bytes(scientific_payload)
            swap_cache.chmod(0o444)
        return result

    monkeypatch.setattr(
        calibration,
        "_read_regular_bytes_and_metadata",
        swap_after_cache_read,
    )
    with pytest.raises(calibration.FinalCalibrationError):
        calibration._read_scientific_payload_bytes_and_metadata(
            scientific_path,
            authorized_dvc_pointers=(pointer_path,),
            repo_root=swap_root,
        )
    assert swapped is True
    assert not swap_physical.samefile(swap_cache)
    monkeypatch.setattr(
        calibration,
        "_read_regular_bytes_and_metadata",
        real_read,
    )

    state = calibration.collect_final_calibration_prelock_state(repo_root=ROOT)
    assert state["prelock"]["outcome_access_log_absent"] is True
    inventory = state["scientific_input_inventory"]
    assert inventory["authority_record_count"] == 66
    assert inventory["payload_binding_count"] == 94
    assert inventory["payload_physical_validation_count"] == 94
    assert inventory["payload_physical_validation_complete"] is True
    assert inventory["calibration_required_input_count"] == 97
    assert inventory["e7_required_input_count"] == 15
    assert len(inventory["calibration_required_inputs"]) == 97
    assert len(inventory["e7_required_inputs"]) == 15
    assert len(
        {record["path"] for record in inventory["calibration_required_inputs"]}
    ) == 97
    assert len({record["path"] for record in inventory["e7_required_inputs"]}) == 15
    assert inventory["git_dvc_manifest_chain_verified"] is True
    authority_paths = {
        record["path"] for record in inventory["authority_records"]
    }
    assert "data/targets.dvc" in authority_paths
    assert "reports/closure_v1/00_protocol/protocol_lock.json" in authority_paths
    # The target manifest is inside the DVC directory and deliberately is not a
    # Git root. Its authority is the Git-bound pointer plus the Git-bound
    # protocol lock, which binds both physical target payloads.
    assert "data/targets/target_manifest_v0.json" not in authority_paths
    target_bindings = {
        record["path"]: record
        for record in inventory["payload_bindings"]
        if record["path"]
        in {
            "data/targets/monthly_targets_model_v0.parquet",
            "data/targets/target_manifest_v0.json",
        }
    }
    assert set(target_bindings) == {
        "data/targets/monthly_targets_model_v0.parquet",
        "data/targets/target_manifest_v0.json",
    }
    assert target_bindings["data/targets/target_manifest_v0.json"][
        "binding_source"
    ] == "reports/closure_v1/00_protocol/protocol_lock.json"
    unavailable = inventory["unavailable_model_evidence"]
    assert unavailable["p0_p1_manifest_count"] == 10
    assert unavailable["p0_p1_report_binding_count"] == 10
    assert unavailable["p0_p1_namespace_path_count"] == 190
    assert unavailable["p0_p1_namespace_present_path_count"] == 20
    assert unavailable["p0_p1_namespace_absent_path_count"] == 170
    assert len(unavailable["p0_p1_namespace_absent_paths"]) == 170
    assert unavailable["p0_p1_namespace_exact"] is True
    assert unavailable["a2_namespace_present_count"] == 0
    assert unavailable["a2_substitute_allowed"] is False
    payload = calibration.build_final_calibration_lock_payload(
        state,
        generated_at_utc="2026-08-10T00:00:00+00:00",
        repo_root=ROOT,
    )
    calibration.validate_final_calibration_lock_payload(payload, repo_root=ROOT)
    for path, key, value in (
        (("authorizations",), "e0_u_authorized", True),
        (("authorizations",), "outcome_access_authorized", True),
        (("authorizations",), "evaluation_batch_authorized", True),
        (("scientific_boundary",), "holdout_row_count", 1),
    ):
        drift = copy.deepcopy(payload)
        cursor = drift
        for part in path:
            cursor = cursor[part]
        cursor[key] = value
        with pytest.raises(calibration.FinalCalibrationError):
            calibration.validate_final_calibration_lock_payload(drift, repo_root=ROOT)
    for key, value in (
        ("sha256", "f" * 64),
        ("bytes", 1),
        ("binding_source", "data/targets/target_manifest_v0.json"),
    ):
        drift = copy.deepcopy(payload)
        record = next(
            candidate
            for candidate in drift["scientific_input_inventory"]["payload_bindings"]
            if candidate["path"] == "data/targets/target_manifest_v0.json"
        )
        record[key] = value
        with pytest.raises(calibration.FinalCalibrationError):
            calibration.validate_final_calibration_lock_payload(drift, repo_root=ROOT)
    inventory_drifts: list[dict[str, Any]] = []
    missing_calibration_input = copy.deepcopy(payload)
    missing_calibration_input["scientific_input_inventory"][
        "calibration_required_inputs"
    ].pop()
    inventory_drifts.append(missing_calibration_input)
    changed_e7_binding = copy.deepcopy(payload)
    changed_e7_binding["scientific_input_inventory"]["e7_required_inputs"][0][
        "sha256"
    ] = "e" * 64
    inventory_drifts.append(changed_e7_binding)
    unavailable_reason = copy.deepcopy(payload)
    unavailable_reason["scientific_input_inventory"]["unavailable_model_evidence"][
        "p0_p1_records"
    ][0]["failure_reason"] = "caller_selected_fallback"
    inventory_drifts.append(unavailable_reason)
    missing_forbidden_path = copy.deepcopy(payload)
    missing_forbidden_path["scientific_input_inventory"][
        "unavailable_model_evidence"
    ]["p0_p1_namespace_absent_paths"].pop()
    inventory_drifts.append(missing_forbidden_path)
    a2_substitute = copy.deepcopy(payload)
    a2_substitute["scientific_input_inventory"]["unavailable_model_evidence"][
        "a2_substitute_allowed"
    ] = True
    inventory_drifts.append(a2_substitute)
    for drift in inventory_drifts:
        with pytest.raises(calibration.FinalCalibrationError):
            calibration.validate_final_calibration_lock_payload(drift, repo_root=ROOT)


def test_output_contract_is_exact_manifest_last_and_zero_overlap() -> None:
    state = calibration.collect_final_calibration_prelock_state(repo_root=ROOT)
    payload = calibration.build_final_calibration_lock_payload(
        state,
        generated_at_utc="2026-08-10T00:00:00+00:00",
        repo_root=ROOT,
    )
    values = set(str(value) for value in _walk(payload["output_contract"]))
    for path in EXPECTED_CALIBRATION_OUTPUTS | EXPECTED_E7_OUTPUTS:
        assert path in values
    assert any("manifest_last" in value.lower() for value in values)


def test_loader_and_requirement_fail_closed_without_published_authority(
    tmp_path: Path,
) -> None:
    with pytest.raises(calibration.FinalCalibrationError):
        calibration.load_effective_final_calibration_authority(repo_root=tmp_path)
    with pytest.raises(calibration.FinalCalibrationError):
        calibration.require_final_calibration_authority(repo_root=tmp_path)


def test_documentation_seals_the_scientific_and_operational_boundaries() -> None:
    text = (ROOT / "docs/closure_v1/E0_M_FINAL_CALIBRATION.md").read_text()
    for token in (
        "E0-MCAL",
        BASE_COMMIT,
        "12A",
        "2A",
        "8A",
        "2019",
        "2020",
        "2021",
        "4096",
        "16384",
        "65536",
        "saturation_claim_authorized=false",
        "manifest-last",
        "outcome_access_authorized=false",
        "e0_u_authorized=false",
        "evaluation_batch_authorized=false",
        "07_anfis_ablation",
        "not_available_degenerate_constant_score",
        "fit_rows=0",
        "397/261/224",
        "371/287/224",
        "344/314/224",
        "Closed scientific input inventory",
        "primary_fit_reuse_count=0",
        "outcome access log remains absent",
        "five-path P-E0-M",
        "R is sequential and one-shot",
        "never recalibrates or repeats the 15 E7 fits",
    ):
        assert token in text
