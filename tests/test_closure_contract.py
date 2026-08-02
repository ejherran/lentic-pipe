from __future__ import annotations

import copy
import subprocess
from collections.abc import MutableMapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from src.experiments import closure_contract, lock_closure_protocol
from src.experiments.closure_contract import (
    DEFAULT_ANALYSIS_PLAN,
    DEFAULT_ANALYSIS_SCHEMA,
    ClosureContractError,
    load_and_validate_analysis_plan,
    load_json_mapping,
    load_yaml_mapping,
    repository_relative,
    validate_analysis_plan,
    validate_json_schema,
)
from src.experiments.lock_closure_protocol import build_lock_payload, dvc_inventory


PUBLIC_CONFIG_PATHS = [
    Path("configs/closure_v1/analysis_plan.yaml"),
    Path("configs/closure_v1/surface_primary.yaml"),
    Path("configs/closure_v1/surface_secondary.yaml"),
    Path("configs/closure_v1/location_holdout.yaml"),
    Path("configs/closure_v1/model_benchmark.yaml"),
    Path("configs/closure_v1/experimental_matrix.yaml"),
]


def _set_nested(payload: MutableMapping[str, Any], path: Sequence[str], value: Any) -> None:
    current = payload
    for key in path[:-1]:
        child = current[key]
        assert isinstance(child, MutableMapping)
        current = child
    current[path[-1]] = value


def test_public_plan_and_referenced_configs_validate_without_outcome_access() -> None:
    plan, summary = load_and_validate_analysis_plan(
        DEFAULT_ANALYSIS_PLAN,
        require_files=True,
        reject_unresolved=True,
    )

    assert summary["experiment_id"] == "closure_v1"
    assert summary["plan_version"] == "1.1"
    assert summary["protocol_status"] == "ready_to_lock"
    assert plan["outcome_access"]["holdout_outcomes_accessed"] is False
    for path in PUBLIC_CONFIG_PATHS:
        assert load_yaml_mapping(path)


def test_public_plan_and_json_schema_parse_and_use_draft_2020_12() -> None:
    plan = load_yaml_mapping(DEFAULT_ANALYSIS_PLAN)
    schema = load_json_mapping(DEFAULT_ANALYSIS_SCHEMA)

    assert plan["schema_version"] == "closure_analysis_plan_v1_1"
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["type"] == "object"


def test_json_schema_rejects_top_level_property_not_seen_by_manual_contract() -> None:
    plan = load_yaml_mapping(DEFAULT_ANALYSIS_PLAN)
    plan["schema_only_invalid_property"] = "must be rejected"

    with pytest.raises(ClosureContractError, match="additionalProperties"):
        validate_analysis_plan(plan, require_files=True, reject_unresolved=True)


def test_json_schema_rejects_unsupported_structural_keyword() -> None:
    plan = load_yaml_mapping(DEFAULT_ANALYSIS_PLAN)
    schema = load_json_mapping(DEFAULT_ANALYSIS_SCHEMA)
    _set_nested(schema, ("properties", "protocol", "anyOf"), [])

    with pytest.raises(ClosureContractError, match="Unsupported JSON Schema keyword"):
        validate_json_schema(plan, schema)


def test_json_schema_rejects_duplicate_enum_values() -> None:
    plan = load_yaml_mapping(DEFAULT_ANALYSIS_PLAN)
    schema = load_json_mapping(DEFAULT_ANALYSIS_SCHEMA)
    schema["properties"]["experiment_id"]["enum"] = ["closure_v1", "closure_v1"]

    with pytest.raises(ClosureContractError, match="enum contains duplicate"):
        validate_json_schema(plan, schema)


def test_json_schema_rejects_duplicate_protocol_component_beyond_fixed_tuple() -> None:
    plan = load_yaml_mapping(DEFAULT_ANALYSIS_PLAN)
    components = plan["locking"]["protocol_components"]
    components.append(components[0])

    with pytest.raises(ClosureContractError, match="ordered component list|maxItems|uniqueItems"):
        validate_analysis_plan(plan, require_files=True, reject_unresolved=True)


@pytest.mark.parametrize(
    ("path", "invalid_value"),
    [
        (("holdout", "unit_type"), "waterbody"),
        (("holdout", "waterbody_claim_authorized"), True),
        (("holdout", "external_validation_claim_authorized"), True),
        (("protocol", "claim_authorizations", "unseen_waterbody_transfer"), True),
        (("time_roles", "training", "target_end"), "2019-01"),
        (("seeds", "values"), [1729]),
        (("outcome_access", "semantic_access_scope"), "physical_storage_pages"),
        (
            ("cohorts", "denominators"),
            [
                "assigned_units",
                "intent_to_predict_origins",
                "metric_evaluable_origins",
            ],
        ),
    ],
    ids=[
        "holdout-unit",
        "waterbody-claim",
        "external-validation-claim",
        "unseen-waterbody-transfer-claim",
        "time-role",
        "seeds",
        "outcome-access-scope",
        "denominators",
    ],
)
def test_locked_decisions_reject_material_mutations(
    path: tuple[str, ...],
    invalid_value: Any,
) -> None:
    plan, _ = load_and_validate_analysis_plan(
        DEFAULT_ANALYSIS_PLAN,
        require_files=True,
        reject_unresolved=True,
    )
    mutated = copy.deepcopy(plan)
    _set_nested(mutated, path, invalid_value)

    with pytest.raises(ClosureContractError):
        validate_analysis_plan(mutated, require_files=False, reject_unresolved=True)


def test_analysis_plan_rejects_family_e_scope_drift() -> None:
    plan = load_yaml_mapping(DEFAULT_ANALYSIS_PLAN)
    plan["hypotheses"]["additional_predeclared_families"][2]["comparison_rule"] = (
        "all_nominal_levels_confirmatory"
    )

    with pytest.raises(ClosureContractError):
        validate_analysis_plan(plan, require_files=False, reject_unresolved=True)


@pytest.mark.parametrize(
    ("field_path", "invalid_value"),
    [
        (("chlorophyll_contract", "current_chla_in_inputs"), True),
        (("chlorophyll_contract", "observed_chla_at_any_input_lag"), "allowed"),
        (("forbidden_predictors",), ["future_target"]),
    ],
)
def test_primary_surface_rejects_observed_chla_lineage(
    monkeypatch: pytest.MonkeyPatch,
    field_path: tuple[str, ...],
    invalid_value: Any,
) -> None:
    plan, _ = load_and_validate_analysis_plan(
        DEFAULT_ANALYSIS_PLAN,
        require_files=True,
        reject_unresolved=True,
    )
    primary_path = plan["surfaces"]["primary"]["config"]
    primary = copy.deepcopy(load_yaml_mapping(primary_path))
    _set_nested(primary, field_path, invalid_value)
    real_loader = closure_contract.load_yaml_mapping

    def load_with_contaminated_primary(path: str | Path) -> dict[str, Any]:
        if repository_relative(path) == repository_relative(primary_path):
            return copy.deepcopy(primary)
        return real_loader(path)

    monkeypatch.setattr(closure_contract, "load_yaml_mapping", load_with_contaminated_primary)

    with pytest.raises(ClosureContractError):
        validate_analysis_plan(plan, require_files=True, reject_unresolved=True)


@pytest.mark.parametrize("unresolved", [None, "auto", "TBD"])
def test_lock_validation_rejects_unresolved_decisions(unresolved: Any) -> None:
    plan, _ = load_and_validate_analysis_plan(
        DEFAULT_ANALYSIS_PLAN,
        require_files=True,
        reject_unresolved=True,
    )
    mutated = copy.deepcopy(plan)
    mutated["protocol"]["status"] = "locked"
    mutated["calibration"]["unresolved_decision_probe"] = unresolved

    with pytest.raises(ClosureContractError, match="unresolved decisions"):
        validate_analysis_plan(mutated, require_files=False, reject_unresolved=True)


def test_protocol_component_list_includes_selector_and_lock_implementation() -> None:
    _, summary = load_and_validate_analysis_plan(
        DEFAULT_ANALYSIS_PLAN,
        require_files=True,
        reject_unresolved=True,
    )

    components = set(summary["protocol_components"])
    assert "src/experiments/build_closure_holdout.py" in components
    assert "src/experiments/lock_closure_protocol.py" in components
    assert "configs/closure_v1/experimental_matrix.yaml" in components


def test_experimental_matrix_rejects_unlocked_combined_severe_ablation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    matrix = load_yaml_mapping("configs/closure_v1/experimental_matrix.yaml")
    severe = next(
        scenario
        for scenario in matrix["e6_matched_degradation"]["scenarios"]
        if scenario["scenario_id"] == "combined_severe"
    )
    severe["components"][-1] = "ablate_light"
    real_loader = closure_contract.load_yaml_mapping

    def load_with_mutated_matrix(path: str | Path) -> dict[str, Any]:
        if repository_relative(path) == "configs/closure_v1/experimental_matrix.yaml":
            return copy.deepcopy(matrix)
        return real_loader(path)

    monkeypatch.setattr(closure_contract, "load_yaml_mapping", load_with_mutated_matrix)
    with pytest.raises(ClosureContractError, match="combined_severe"):
        load_and_validate_analysis_plan(
            DEFAULT_ANALYSIS_PLAN,
            require_files=True,
            reject_unresolved=True,
        )


@pytest.mark.parametrize(
    ("field_path", "invalid_value"),
    [
        (
            (
                "e6_matched_degradation",
                "mask_contract",
                "digest_to_unit_interval",
                "divisor",
            ),
            10,
        ),
        (
            (
                "e6_matched_degradation",
                "mask_contract",
                "digest_payload_types_in_order",
            ),
            ["all_json_strings"],
        ),
        (
            (
                "e6_matched_degradation",
                "mask_contract",
                "temporal_block_rule",
                "overlap_within_series",
            ),
            "allowed",
        ),
        (
            (
                "e6_matched_degradation",
                "replicate_contract",
                "model_seed_by_degradation_seed_cross_product",
            ),
            "required",
        ),
        (
            (
                "e8_uncertainty",
                "continuous_interval_recalibration",
                "calibration_period",
                "end",
            ),
            "2022-12",
        ),
        (
            (
                "e8_uncertainty",
                "continuous_interval_recalibration",
                "pooling_across_groups",
            ),
            "allowed",
        ),
        (
            ("e8_uncertainty", "conditional_coverage", "evaluation_role"),
            "model_selection",
        ),
        (
            ("e8_uncertainty", "confirmatory_family_E", "p_value_universe_size"),
            27,
        ),
        (
            ("e9_planning_inference", "objective_contract", "base_penalties"),
            {"lambda_cost": 0.0, "lambda_uncertainty": 0.10, "lambda_support": 0.05},
        ),
        (
            (
                "e9_planning_inference",
                "objective_contract",
                "legacy_planning_mode_and_budget_reused",
            ),
            True,
        ),
        (
            (
                "e9_planning_inference",
                "confirmatory_family_D",
                "primary_action_estimand",
            ),
            "best_horizon_only",
        ),
        (
            ("e9_planning_inference", "model_contract", "seeds_are_inference_units"),
            True,
        ),
    ],
    ids=[
        "e6-digest-map",
        "e6-digest-types",
        "e6-block-overlap",
        "e6-seed-pairing",
        "e8-period",
        "e8-no-pooling",
        "e8-evaluation-role",
        "e8-family-E-universe",
        "e9-penalties",
        "e9-no-legacy-budget",
        "e9-estimand",
        "e9-seed-aggregation",
    ],
)
def test_experimental_matrix_rejects_material_algorithm_mutations(
    monkeypatch: pytest.MonkeyPatch,
    field_path: tuple[str, ...],
    invalid_value: Any,
) -> None:
    matrix = load_yaml_mapping("configs/closure_v1/experimental_matrix.yaml")
    _set_nested(matrix, field_path, invalid_value)
    real_loader = closure_contract.load_yaml_mapping

    def load_with_mutated_matrix(path: str | Path) -> dict[str, Any]:
        if repository_relative(path) == "configs/closure_v1/experimental_matrix.yaml":
            return copy.deepcopy(matrix)
        return real_loader(path)

    monkeypatch.setattr(closure_contract, "load_yaml_mapping", load_with_mutated_matrix)
    with pytest.raises(ClosureContractError):
        load_and_validate_analysis_plan(
            DEFAULT_ANALYSIS_PLAN,
            require_files=True,
            reject_unresolved=True,
        )


def test_experimental_matrix_rejects_ablation_operation_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    matrix = load_yaml_mapping("configs/closure_v1/experimental_matrix.yaml")
    nutrient_ablation = next(
        scenario
        for scenario in matrix["e6_matched_degradation"]["scenarios"]
        if scenario["scenario_id"] == "ablate_nutrients"
    )
    nutrient_ablation["operation"] = "replace_with_zero"
    real_loader = closure_contract.load_yaml_mapping

    def load_with_mutated_matrix(path: str | Path) -> dict[str, Any]:
        if repository_relative(path) == "configs/closure_v1/experimental_matrix.yaml":
            return copy.deepcopy(matrix)
        return real_loader(path)

    monkeypatch.setattr(closure_contract, "load_yaml_mapping", load_with_mutated_matrix)
    with pytest.raises(ClosureContractError, match="ablate_nutrients"):
        load_and_validate_analysis_plan(
            DEFAULT_ANALYSIS_PLAN,
            require_files=True,
            reject_unresolved=True,
        )


def test_dvc_inventory_reads_all_64_tracked_pointers_without_remote_access() -> None:
    rows = dvc_inventory()
    pointer_paths = {str(row["pointer_path"]) for row in rows}

    assert len(pointer_paths) == 64
    assert all(row["hash_name"] and row["hash_value"] for row in rows)


def test_protocol_component_guard_rejects_any_untracked_path(monkeypatch: pytest.MonkeyPatch) -> None:
    records: list[dict[str, Any]] = [
        {"path": "tracked-component.txt"},
        {"path": "untracked-component.txt"},
    ]
    commands: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        path = command[-1]
        return subprocess.CompletedProcess(
            command,
            0 if path == "tracked-component.txt" else 1,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(lock_closure_protocol.subprocess, "run", fake_run)

    with pytest.raises(ClosureContractError, match="untracked-component.txt"):
        lock_closure_protocol._assert_protocol_components_tracked(records)

    assert [command[-1] for command in commands] == [
        "tracked-component.txt",
        "untracked-component.txt",
    ]


def test_build_lock_payload_preserves_locked_repository_and_sealed_state() -> None:
    plan = load_yaml_mapping(DEFAULT_ANALYSIS_PLAN)
    plan["protocol"]["status"] = "locked"
    locked_head = "a" * 40
    state = {
        "head": locked_head,
        "branch": "closure-v1-protocol",
        "worktree_status": "clean",
        "dirty_paths": [],
    }

    payload = build_lock_payload(
        plan_path=DEFAULT_ANALYSIS_PLAN,
        plan=plan,
        state=state,
        alignment_base="b" * 40,
        component_records=[],
        source_records=[],
        output_records=[],
        dvc_rows=[],
    )

    assert payload["status"] == "locked"
    assert payload["locked_repository"]["head"] == locked_head
    assert payload["future_outcomes_accessed"] is False
    assert payload["lock_command_reads_complete_source_bytes_for_sha256"] is True
    assert payload["lock_command_semantically_decodes_post_2021_outcomes"] is False
    assert payload["holdout_assignment_created"] is False


def test_protocol_lock_bundle_rolls_back_all_outputs_after_partial_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "protocol-lock"
    plan = {
        "locking": {
            "lock_manifest": (output_dir / "protocol_lock.json").as_posix(),
            "repository_state": (output_dir / "repository_state.json").as_posix(),
        },
        "change_control": {},
    }
    state = {
        "head": "a" * 40,
        "branch": "closure-v1-protocol",
        "worktree_status": "clean",
        "dirty_paths": [],
    }

    monkeypatch.setattr(
        lock_closure_protocol,
        "load_and_validate_analysis_plan",
        lambda *args, **kwargs: (plan, {}),
    )
    monkeypatch.setattr(lock_closure_protocol, "repository_state", lambda: state)
    monkeypatch.setattr(
        lock_closure_protocol,
        "_assert_alignment_base",
        lambda *args, **kwargs: "b" * 40,
    )
    monkeypatch.setattr(lock_closure_protocol, "_component_records", lambda *args: [])
    monkeypatch.setattr(lock_closure_protocol, "_source_artifact_records", lambda *args: [])
    monkeypatch.setattr(lock_closure_protocol, "dvc_inventory", lambda: [])
    monkeypatch.setattr(lock_closure_protocol, "environment_payload", lambda: {})
    monkeypatch.setattr(lock_closure_protocol, "resolve_repo_path", lambda path: Path(path).resolve())
    monkeypatch.setattr(lock_closure_protocol, "repository_relative", lambda path: Path(path).as_posix())

    real_write_csv = lock_closure_protocol._write_csv_atomic

    def write_csv_then_fail(
        rows: list[dict[str, Any]],
        path: Path,
        *,
        fieldnames: list[str],
    ) -> None:
        real_write_csv(rows, path, fieldnames=fieldnames)
        if path.name == "code_hashes.csv":
            raise RuntimeError("injected bundle failure")

    monkeypatch.setattr(lock_closure_protocol, "_write_csv_atomic", write_csv_then_fail)

    with pytest.raises(RuntimeError, match="injected bundle failure"):
        lock_closure_protocol.create_protocol_lock(DEFAULT_ANALYSIS_PLAN, output_dir)

    assert output_dir.is_dir()
    assert not [path for path in output_dir.iterdir() if path.is_file()]
