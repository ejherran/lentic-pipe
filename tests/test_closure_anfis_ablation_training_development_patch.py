from __future__ import annotations

import json
import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.experiments import closure_anfis_ablation_training_development_patch as patch
from src.experiments import audit_closure_anfis_ablation_model_bundle as auditor
from src.experiments import lock_closure_anfis_ablation_training_development_patch as locker


ROOT = Path(__file__).resolve().parents[1]


def _runtime() -> dict[str, Any]:
    payload = yaml.safe_load((ROOT / patch.DEFAULT_RUNTIME_CONFIG).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_runtime_identity_scope_and_physical_inputs_are_closed() -> None:
    runtime = _runtime()
    assert runtime["schema_version"] == "closure_anfis_ablation_training_development_runtime_v1"
    assert runtime["gate"] == "E0-MT"
    assert runtime["patch_base_commit"] == patch.BASE_COMMIT
    scope = runtime["patch_scope"]
    assert scope["exact_added_count"] == 10
    assert scope["exact_modified_count"] == scope["exact_deleted_count"] == 0
    assert tuple(sorted(scope["paths"])) == patch.PATCH_PATHS
    records = runtime["authority"]["physical_inputs"]
    assert runtime["authority"]["physical_input_count"] == 47 == len(records)
    assert len({record["path"] for record in records}) == len(records)
    assert len({record["role"] for record in records}) == len(records)


def test_runtime_target_projection_and_cutoff_are_exact() -> None:
    runtime = _runtime()
    targets = runtime["targets"]
    assert targets["exact_projection"] == [
        "source_id",
        "site_id",
        "origin_year_month",
        "target_year_month",
        "horizon_months",
        "bloom_h",
        "target_risk_chla_h",
    ]
    assert targets["training"] == {"origins": 5932, "rows": 17796}
    assert targets["model_selection"] == {"origins": 658, "rows": 1974}
    assert targets["calibration_threshold_closed"] == {"origins": 224, "rows": 672}
    assert runtime["roles"]["calibration_target_values_opened"] is False
    assert targets["post_2020_target_projection"] == "forbidden"
    assert targets["raw_chlorophyll_projection"] == "forbidden"


def test_runtime_preprocessor_model_and_slots_are_paired() -> None:
    runtime = _runtime()
    preprocessing = runtime["preprocessing"]
    assert preprocessing["fit_role"] == "training"
    assert preprocessing["raw_values"] == "mask_aware_training_standard_scaler_ddof0"
    assert preprocessing["fit_outside_training"] == "forbidden"
    assert len(preprocessing["raw_training_statistics"]) == 7
    architecture = runtime["model"]["common_architecture"]
    assert runtime["model"]["architecture_reference"] == "src/experiments/train_pipe_grud.py"
    assert "implementation_dependency" not in runtime["model"]
    assert architecture["hidden_dimension"] == 96
    assert architecture["recurrent_layers"] == 1
    assert architecture["add_last"] is False
    slots = runtime["slots"]["ordered_slots"]
    assert [(item["model_id"], item["base_seed"]) for item in slots] == list(
        patch.ORDERED_SLOTS
    )


def test_runtime_output_namespace_and_authorizations_are_closed() -> None:
    runtime = _runtime()
    outputs = runtime["outputs"]
    assert outputs["exact_final_path_count"] == 80
    assert outputs["exact_temporary_path_count"] == 80
    assert outputs["exact_guard_path_count"] == 10
    assert outputs["exact_prediction_pointer_count"] == 10
    assert outputs["transaction"] == {
        "exclusive_guard": True,
        "parent_walk": "dirfd_no_follow",
        "temporary_sibling": True,
        "final_publication": "hardlink_no_clobber",
        "rollback": "owned_inode_only",
        "manifest_written_last": True,
        "authority_stability": {
            "records": ["runtime", "lock", "companion"],
            "verify_before_input_io": True,
            "verify_after_fit": True,
            "verify_before_manifest_publication": True,
            "verify_after_manifest_publication": True,
            "exact_file_record_identity_required": True,
        },
    }
    authorizations = runtime["authorizations"]
    assert authorizations["publication_required"] is True
    assert all(value is False for key, value in authorizations.items() if key != "publication_required")
    audit = patch._effective_authorizations(model_id="A0", mode="audit")
    assert audit["model_bundle_audit_authorized"] is True
    assert audit["target_access_through_2020_authorized"] is True
    assert audit["selection_diagnostics_authorized"] is True
    assert audit["a0_development_fit_authorized"] is False
    assert audit["a1_development_fit_authorized"] is False
    assert all(
        audit[key] is False
        for key in (
            "calibration_authorized",
            "calibration_target_access_authorized",
            "final_e7_metrics_authorized",
            "rollout_authorized",
            "e0_m_authorized",
            "evaluation_authorized",
            "e0_u_authorized",
            "dvc_commands_authorized",
            "scientific_network_authorized",
            "outcome_access_authorized",
            "future_outcomes_accessed",
            "batch_slot_execution_authorized",
        )
    )


@pytest.mark.parametrize(
    ("keys", "replacement"),
    [
        (("targets", "training_bloom_positive_by_horizon", "1"), 1783),
        (("targets", "training_bloom_prevalence_by_horizon", "1"), 0.31),
        (("targets", "training_risk_mean_by_horizon", "1"), 0.59),
        (("preprocessing", "raw_training_statistics", "x_mean_TP_ugL", "observed_cells"), 80270),
        (("model", "common_architecture", "risk_logvar_clamp"), [-9.0, 2.0]),
        (("model", "selection", "checkpoint_objective"), "unsealed_objective"),
        (("outputs", "model_template"), "models/unsealed/{model_id}/{base_seed}.pt"),
        (("outputs", "transaction", "rollback"), "path_based_delete"),
        (("verification", "full_type_check"), ["python", "-c", "pass"]),
        (("unexpected_top_level_key",), True),
    ],
)
def test_runtime_loader_rejects_scientific_mutations(
    tmp_path: Path,
    keys: tuple[str, ...],
    replacement: object,
) -> None:
    runtime = copy.deepcopy(_runtime())
    cursor: dict[str, Any] = runtime
    for key in keys[:-1]:
        child = cursor[key]
        assert isinstance(child, dict)
        cursor = child
    cursor[keys[-1]] = replacement
    path = tmp_path / "runtime.yaml"
    path.write_text(yaml.safe_dump(runtime, sort_keys=False), encoding="utf-8")
    with pytest.raises(patch.AnfisAblationTrainingDevelopmentPatchError):
        patch.load_anfis_ablation_training_runtime(
            Path("runtime.yaml"), verify_physical_pins=False, repo_root=tmp_path
        )


def test_runtime_loader_rejects_substituted_physical_input(tmp_path: Path) -> None:
    runtime = copy.deepcopy(_runtime())
    runtime["patch_id"] = "unsealed_patch_id"
    path = tmp_path / "runtime.yaml"
    path.write_text(yaml.safe_dump(runtime, sort_keys=False), encoding="utf-8")
    with pytest.raises(patch.AnfisAblationTrainingDevelopmentPatchError):
        patch.load_anfis_ablation_training_runtime(
            Path("runtime.yaml"), verify_physical_pins=False, repo_root=tmp_path
        )

    runtime = copy.deepcopy(_runtime())
    authority = runtime["authority"]
    assert isinstance(authority, dict)
    records = authority["physical_inputs"]
    assert isinstance(records, list) and isinstance(records[0], dict)
    records[0]["path"] = "reports/closure_v1/00_protocol/not_the_protocol_lock.json"
    path.write_text(yaml.safe_dump(runtime, sort_keys=False), encoding="utf-8")
    with pytest.raises(patch.AnfisAblationTrainingDevelopmentPatchError):
        patch.load_anfis_ablation_training_runtime(
            Path("runtime.yaml"), verify_physical_pins=False, repo_root=tmp_path
        )


def test_schema_has_unique_required_entries_and_closed_authorizations() -> None:
    payload = json.loads((ROOT / patch.DEFAULT_PATCH_LOCK_SCHEMA).read_text(encoding="utf-8"))
    assert len(payload["required"]) == len(set(payload["required"]))
    closed = payload["$defs"]["closedAuthorizations"]
    assert len(closed["required"]) == len(set(closed["required"]))
    assert closed["additionalProperties"] is False
    assert all(
        definition.get("const") is False
        for key, definition in closed["properties"].items()
        if key != "publication_required"
    )
    assert closed["properties"]["publication_required"]["const"] is True


def test_patch_paths_are_additive_and_do_not_touch_sealed_plans() -> None:
    assert len(patch.PATCH_PATHS) == 10
    assert not any(path.startswith("private/") for path in patch.PATCH_PATHS)
    assert "configs/closure_v1/model_benchmark.yaml" not in patch.PATCH_PATHS
    assert "configs/closure_v1/analysis_plan.yaml" not in patch.PATCH_PATHS
    assert all(not path.endswith(".dvc") for path in patch.PATCH_PATHS)


def test_canonical_json_is_stable_and_rejects_nan() -> None:
    assert patch._canonical_json({"b": 2, "a": 1}) == b'{"a":1,"b":2}\n'
    with pytest.raises(ValueError):
        patch._canonical_json({"bad": float("nan")})


def test_focused_summary_requires_exact_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(patch, "FOCUSED_TEST_COUNT", 17)
    assert locker._parse_focused_summary("17 passed in 0.12s\n", "") == {
        "test_count": 17,
        "skipped_count": 0,
        "deselected_count": 0,
    }
    with pytest.raises(patch.AnfisAblationTrainingDevelopmentPatchError):
        locker._parse_focused_summary("16 passed in 0.12s\n", "")
    with pytest.raises(patch.AnfisAblationTrainingDevelopmentPatchError):
        locker._parse_focused_summary("17 passed, 1 skipped in 0.12s\n", "")


def test_check_only_is_non_writing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        patch,
        "preflight_anfis_ablation_training_development_patch_schema",
        lambda: {"status": "schema_valid"},
    )
    monkeypatch.setattr(
        patch,
        "collect_anfis_ablation_training_development_patch_prelock_state",
        lambda *, verify_remote: {
            "repository": {"head": "a" * 40},
            "h_patch": {"component_count": 10},
            "runtime_contract": {"physical_input_count": 47},
        },
    )
    result = locker.check_only()
    assert result["status"] == "ready_to_lock"
    assert result["writes_performed"] is False
    assert result["verification_commands_run"] is False
    assert result["fit_or_trainer_run"] is False
    assert result["dvc_commands_run"] is False
    assert result["future_outcomes_accessed"] is False


def test_execute_lock_recollects_identical_state_before_publish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {
        "repository": {"head": "a" * 40},
        "h_patch": {"component_count": 10},
        "runtime_contract": {"physical_input_count": 47},
    }
    monkeypatch.setattr(
        patch,
        "preflight_anfis_ablation_training_development_patch_schema",
        lambda: {"status": "schema_valid"},
    )
    monkeypatch.setattr(
        patch,
        "collect_anfis_ablation_training_development_patch_prelock_state",
        lambda *, verify_remote: dict(state),
    )
    monkeypatch.setattr(
        locker,
        "run_anfis_ablation_training_development_patch_verification",
        lambda **kwargs: {"focused_tests": {"test_count": 17}},
    )
    monkeypatch.setattr(
        patch,
        "build_anfis_ablation_training_development_patch_lock_payload",
        lambda *, prelock, verification: {"status": "locked_unpublished"},
    )
    monkeypatch.setattr(
        patch,
        "validate_anfis_ablation_training_development_patch_lock_payload",
        lambda payload: None,
    )
    monkeypatch.setattr(
        patch,
        "publish_anfis_ablation_training_lock_bundle",
        lambda payload: (payload, {"status": "manifest"}),
    )
    result = locker.execute_lock()
    assert result["status"] == "locked_unpublished"
    assert result["fit_or_trainer_run"] is False
    assert result["auditor_run"] is False


def test_execute_lock_rejects_prelock_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    states = iter([{"value": 1}, {"value": 2}])
    monkeypatch.setattr(
        patch,
        "preflight_anfis_ablation_training_development_patch_schema",
        lambda: {"status": "schema_valid"},
    )
    monkeypatch.setattr(
        patch,
        "collect_anfis_ablation_training_development_patch_prelock_state",
        lambda *, verify_remote: next(states),
    )
    monkeypatch.setattr(
        locker,
        "run_anfis_ablation_training_development_patch_verification",
        lambda **kwargs: {},
    )
    with pytest.raises(
        patch.AnfisAblationTrainingDevelopmentPatchError,
        match="changed during verification",
    ):
        locker.execute_lock()


def test_publication_marker_is_exact() -> None:
    locker._require_publication_guard_success(
        "Checking tracked files before publication...\n"
        "OK: tracked files look publication-ready.\n",
        "",
    )
    with pytest.raises(patch.AnfisAblationTrainingDevelopmentPatchError):
        locker._require_publication_guard_success(
            "OK: tracked files look publication-ready.\n", ""
        )


def test_publication_guard_rejects_lexical_parent_replacement(
    tmp_path: Path,
) -> None:
    guard_path = Path("tmp/lock_bundle.guard")
    guard = patch._acquire_publication_guard(
        guard_path,
        b"owned guard\n",
        repo_root=tmp_path,
    )
    original_parent = tmp_path / "tmp"
    detached_parent = tmp_path / "detached_tmp"
    original_parent.rename(detached_parent)
    original_parent.mkdir()
    foreign = original_parent / guard_path.name
    foreign.write_bytes(b"foreign")

    with pytest.raises(
        patch.AnfisAblationTrainingDevelopmentPatchError,
        match="guard identity drifted",
    ):
        patch._release_publication_guard(guard)
    assert foreign.read_bytes() == b"foreign"


def test_owned_outputs_rollback_through_retained_parent_after_swap(
    tmp_path: Path,
) -> None:
    lock_path = Path("reports/protocol/lock.json")
    companion_path = Path("reports/protocol/lock_manifest.json")
    lock = patch._publish_bytes_no_clobber(
        lock_path,
        b"lock\n",
        repo_root=tmp_path,
    )
    lexical_parent = tmp_path / lock_path.parent
    detached_parent = tmp_path / "detached_protocol"
    lexical_parent.rename(detached_parent)
    lexical_parent.mkdir(parents=True)
    foreign = lexical_parent / lock_path.name
    foreign.write_bytes(b"foreign")
    companion = patch._publish_bytes_no_clobber(
        companion_path,
        b"companion\n",
        repo_root=tmp_path,
    )

    with pytest.raises(
        patch.AnfisAblationTrainingDevelopmentPatchError,
        match="owned output identity drifted",
    ):
        patch._validate_owned_output(lock)
    patch._rollback_owned_output(companion)
    patch._rollback_owned_output(lock)

    assert foreign.read_bytes() == b"foreign"
    assert not (lexical_parent / companion_path.name).exists()
    assert not (detached_parent / lock_path.name).exists()


def test_lock_bundle_rolls_back_if_guard_release_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock_path = Path("reports/protocol/lock.json")
    companion_path = Path("reports/protocol/lock_manifest.json")
    guard_path = Path("tmp/lock_bundle.guard")
    monkeypatch.setattr(patch, "DEFAULT_PATCH_LOCK_PATH", lock_path)
    monkeypatch.setattr(patch, "DEFAULT_PATCH_LOCK_MANIFEST_PATH", companion_path)
    monkeypatch.setattr(patch, "LOCKER_GUARD_PATH", guard_path)
    monkeypatch.setattr(
        patch,
        "validate_anfis_ablation_training_development_patch_lock_payload",
        lambda payload, **kwargs: None,
    )
    monkeypatch.setattr(
        patch,
        "_expected_companion",
        lambda payload, lock_record, **kwargs: {
            "status": "completed",
            "completion_marker_written_last": True,
        },
    )
    release = patch._release_publication_guard

    def fail_strict_release(
        guard: patch._OwnedGuard,
        *,
        tolerate_foreign: bool = False,
    ) -> None:
        if not tolerate_foreign:
            raise patch.AnfisAblationTrainingDevelopmentPatchError(
                "injected guard release failure"
            )
        release(guard, tolerate_foreign=True)

    monkeypatch.setattr(patch, "_release_publication_guard", fail_strict_release)

    with pytest.raises(
        patch.AnfisAblationTrainingDevelopmentPatchError,
        match="injected guard release failure",
    ):
        patch.publish_anfis_ablation_training_lock_bundle(
            {"status": "locked_unpublished"},
            repo_root=tmp_path,
        )

    assert not (tmp_path / lock_path).exists()
    assert not (tmp_path / companion_path).exists()
    assert not (tmp_path / Path(lock_path.as_posix() + ".tmp")).exists()
    assert not (tmp_path / Path(companion_path.as_posix() + ".tmp")).exists()
    assert not (tmp_path / guard_path).exists()


def test_prefix_propagates_completed_slot_semantic_rejection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_id, base_seed = patch.ORDERED_SLOTS[0]
    target_index = 0
    runtime: dict[str, Any] = {
        "targets": {
            "join_columns": ["source_id"],
            "exact_projection": ["source_id", "bloom_h", "target_risk_chla_h"],
            "horizons_months": [1, 2, 3],
            "training": {"origins": 5932, "rows": 17796},
            "model_selection": {"origins": 658, "rows": 1974},
            "calibration_threshold_closed": {"origins": 224, "rows": 672},
        },
        "roles": {"model_selection_end": "2020-12"},
        "preprocessing": {"fit_role": "training"},
        "model": {
            "family": "gru_direct_prior_residual",
            "common_architecture": {"hidden_dimension": 96},
            "loss": {"heads": 3},
            "selection": {"checkpoint_tie_break": "earliest_epoch"},
            "optimization": {"maximum_epochs": 20},
            "execution": {"device": "cpu"},
        },
        "inputs": {
            "history_length_months": 12,
            model_id: {"input_dimension": 18},
        },
    }
    static: dict[str, Any] = {
        "gate": "E0-MT",
        "status": "effective_preflight_passed",
        "h_patch_head": "a" * 40,
        "p_patch_head": "b" * 40,
        "h_components_sha256": "c" * 64,
        "physical_inputs_sha256": "d" * 64,
        "runtime_sha256": "e" * 64,
        "lock_sha256": "f" * 64,
        "companion_sha256": "0" * 64,
    }

    def record(path: Path, *, role: str, repo_root: Path) -> dict[str, Any]:
        del repo_root
        return {
            "role": role,
            "path": path.as_posix(),
            "bytes": 1,
            "sha256": "1" * 64,
        }

    expected_authority = {
        **static,
        "authorized_model_id": model_id,
        "authorized_base_seed": base_seed,
        "completed_prefix_count": target_index,
        "slot_creation_prefix_count": target_index,
    }
    input_records = [
        record(path, role=role, repo_root=tmp_path)
        for role, path in patch._manifest_input_spec(model_id, base_seed)
    ]
    paths = patch.anfis_ablation_training_slot_paths(model_id, base_seed)
    output_records = [
        record(paths[name], role=name, repo_root=tmp_path)
        for name in (
            "model",
            "checkpoint",
            "preprocessor",
            "training_curve",
            "selection_predictions",
            "selection_metrics",
            "report",
        )
    ]
    trainer_record = record(
        Path("src/experiments/train_closure_anfis_ablation.py"),
        role="trainer",
        repo_root=tmp_path,
    )
    manifest: dict[str, Any] = {
        "manifest_version": "closure_anfis_ablation_model_manifest_v1",
        "status": "completed",
        "slot_status": "available",
        "fit_status": "passed",
        "generated_at_utc": "2026-08-08T00:00:00Z",
        "experiment_id": "closure_v1",
        "surface_id": "closure_v1_wqp_adaptive_no_current_chla",
        "model_id": model_id,
        "base_seed": base_seed,
        "device": "cpu",
        "future_outcomes_accessed": False,
        "calibration_authorized": False,
        "calibration_target_accessed": False,
        "evaluation_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "dvc_command_executed": False,
        "target_contract": {
            "join_columns": ["source_id"],
            "exact_projection": ["source_id", "bloom_h", "target_risk_chla_h"],
            "horizons_months": [1, 2, 3],
            "development_target_access_end": "2020-12",
            "calibration_target_values_opened": False,
            "raw_chlorophyll_projection": "forbidden",
        },
        "role_counts": {
            "training": {"origins": 5932, "rows": 17796},
            "model_selection": {"origins": 658, "rows": 1974},
            "calibration_threshold_metadata_only": {"origins": 224, "rows": 672},
            "calibration_target_rows_read": 0,
            "test_target_rows_read": 0,
            "holdout_target_rows_read": 0,
            "post_2020_target_rows_read": 0,
        },
        "architecture": {
            "history_length_months": 12,
            "input_dimension": 18,
            "family": "gru_direct_prior_residual",
            "common_architecture": {"hidden_dimension": 96},
            "loss": {"heads": 3},
            "selection": {"checkpoint_tie_break": "earliest_epoch"},
            "optimization": {"maximum_epochs": 20},
            "execution": {"device": "cpu"},
        },
        "preprocessing": {"fit_role": "training"},
        "pairing": {
            "policy": "same_model_seed_pair_A0_then_A1",
            "paired_model_ids": ["A0", "A1"],
            "base_seed": base_seed,
            "training_identity_sha256": "2" * 64,
            "selection_identity_sha256": "3" * 64,
            "selection_target_sha256": "4" * 64,
        },
        "authority": expected_authority,
        "authority_records": [],
        "script": trainer_record,
        "inputs": input_records,
        "source_code": [trainer_record],
        "outputs": output_records,
        "completion_marker_written_last": True,
    }

    monkeypatch.setattr(
        patch,
        "load_anfis_ablation_training_runtime",
        lambda **kwargs: runtime,
    )
    monkeypatch.setattr(patch, "_plain_record", record)
    monkeypatch.setattr(patch, "_load_json", lambda *args, **kwargs: manifest)
    monkeypatch.setattr(
        patch,
        "_read_regular_bytes",
        lambda *args, **kwargs: patch._canonical_json(manifest),
    )
    monkeypatch.setattr(
        auditor,
        "load_cutoff_target_reference",
        lambda **kwargs: object(),
    )

    def reject_semantics(**kwargs: object) -> dict[str, Any]:
        del kwargs
        raise auditor.AnfisAblationModelAuditError("injected semantic rejection")

    monkeypatch.setattr(
        auditor,
        "validate_anfis_ablation_model_bundle_semantics",
        reject_semantics,
    )
    first_slot_paths = set(paths.values())
    monkeypatch.setattr(
        patch,
        "_lexists",
        lambda path: path.relative_to(tmp_path) in first_slot_paths,
    )

    with pytest.raises(
        patch.AnfisAblationTrainingDevelopmentPatchError,
        match="completed slot failed semantic audit",
    ):
        patch._validate_exact_training_prefix(
            static,
            audit_mode=False,
            repo_root=tmp_path,
        )
