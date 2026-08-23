from __future__ import annotations

import copy
import json

import pytest
import yaml

from src.experiments.closure_contract import ClosureContractError, validate_json_schema
from src.experiments.closure_v2 import contracts


def test_published_analysis_plan_and_semantics_pass() -> None:
    plan = contracts.validate_analysis_plan()
    assert plan["seeds"] == contracts.EXPECTED_SEEDS
    assert plan["denominators"] == contracts.EXPECTED_DENOMINATORS


def test_published_eligibility_policy_passes() -> None:
    policy = contracts.validate_eligibility_policy()
    assert policy["authorization_thresholds"]["minimum_overall_fit_eligibility_fraction"] == 0.9


def test_complete_protocol_is_ready_to_lock() -> None:
    result = contracts.validate_protocol()
    assert result["v1_audit"]["protected_v1_changes"] == []
    assert result["evaluation_cohorts"]["selection"]["selected_if_post_model_lock_reconstruction_matches"] == "fresh_location"


def test_schema_rejects_seed_drift() -> None:
    plan = yaml.safe_load((contracts.PROJECT_ROOT / contracts.ANALYSIS_PLAN).read_text())
    schema = json.loads((contracts.PROJECT_ROOT / contracts.ANALYSIS_SCHEMA).read_text())
    changed = copy.deepcopy(plan)
    changed["seeds"][-1] = 7
    with pytest.raises(ClosureContractError):
        validate_json_schema(changed, schema, instance_path="$.analysis_plan")


def test_semantics_reject_outcome_access_before_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = yaml.safe_load((contracts.PROJECT_ROOT / contracts.ANALYSIS_PLAN).read_text())
    plan["outcome_access"]["before_model_lock"] = "allowed"
    monkeypatch.setattr(contracts, "load_yaml_mapping", lambda _: plan)
    with pytest.raises(ClosureContractError, match="before_model_lock"):
        contracts.validate_analysis_plan()


def test_fresh_location_feasibility_is_above_locked_minimums() -> None:
    cohorts = contracts.validate_evaluation_cohorts()
    fresh = cohorts["fresh_location"]
    audit = fresh["prelock_input_only_feasibility_audit"]
    assert audit["candidate_location_count"] >= fresh["minimum_new_locations"]
    assert audit["intent_origins_per_horizon"] >= fresh["minimum_intent_origins_per_horizon"]
    assert audit["target_paths_opened"] is False


def test_artifact_inventory_is_unique_and_v2_scoped() -> None:
    assert len(contracts.ARTIFACT_PATHS) == len(set(contracts.ARTIFACT_PATHS))
    assert all("closure_v2" in path for path in contracts.ARTIFACT_PATHS)


def test_protocol_components_exist_and_are_v2_or_auditor() -> None:
    for relative in contracts.PROTOCOL_COMPONENTS:
        assert (contracts.PROJECT_ROOT / relative).is_file()
        assert "closure_v2" in relative.as_posix()


def test_reference_manifest_is_generic_checker_compatible() -> None:
    manifest = json.loads((contracts.PROJECT_ROOT / contracts.REFERENCE_MANIFEST).read_text())
    assert manifest["status"] == "completed"
    assert manifest["outputs"]
    assert all({"path", "bytes", "sha256"}.issubset(record) for record in manifest["outputs"])
