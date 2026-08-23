#!/usr/bin/env python
"""Validate and lock the outcome-free Closure V2 protocol."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from src.experiments.closure_contract import (
    ClosureContractError,
    load_json_mapping,
    load_yaml_mapping,
    validate_json_schema,
)
from src.experiments.closure_v2.audit_v1_inputs import (
    EXPECTED_CERTIFICATION_COMMIT,
    EXPECTED_EDITORIAL_COMMIT,
    EXPECTED_SCIENCE_COMMIT,
    EXPECTED_SYNTHESIS_COMMIT,
    EXPECTED_TAG_OBJECT,
    PROJECT_ROOT,
    audit_repository,
    sha256_file,
)


ANALYSIS_PLAN = Path("configs/closure_v2/analysis_plan.yaml")
ANALYSIS_SCHEMA = Path("configs/closure_v2/analysis_plan.schema.json")
ELIGIBILITY_POLICY = Path("configs/closure_v2/eligibility_policy.yaml")
ELIGIBILITY_SCHEMA = Path("configs/closure_v2/eligibility_policy.schema.json")
PROTOCOL_LOCK = Path("reports/closure_v2/00_protocol/protocol_lock.json")
ARTIFACT_INVENTORY = Path("reports/closure_v2/00_protocol/artifact_inventory.csv")
REFERENCE_MANIFEST = Path("reports/closure_v2/00_protocol/v1_reference_manifest.json")
PROTOCOL_REPORT_OUTPUTS = (
    Path("reports/closure_v2/00_protocol/EXECUTION_LOG.md"),
    ARTIFACT_INVENTORY,
    Path("reports/closure_v2/00_protocol/entry_receipt.json"),
    Path("reports/closure_v2/00_protocol/implementation_state.json"),
    PROTOCOL_LOCK,
)
EXPECTED_SEEDS = [1729, 20260612, 20260613, 20260614, 314159]
EXPECTED_DENOMINATORS = [
    "attempted",
    "input_eligible",
    "prediction_successful",
    "target_available",
    "metric_evaluable",
    "shared_success",
]
PROTOCOL_COMPONENTS = (
    Path("docs/closure_v2/EXECUTION_GUIDE.md"),
    Path("docs/closure_v2/ANALYSIS_PLAN.md"),
    Path("docs/closure_v2/PROTOCOL_AMENDMENT_V2.md"),
    Path("docs/closure_v2/CLAIM_BOUNDARIES.md"),
    ANALYSIS_PLAN,
    ANALYSIS_SCHEMA,
    ELIGIBILITY_POLICY,
    ELIGIBILITY_SCHEMA,
    Path("configs/closure_v2/model_benchmark.yaml"),
    Path("configs/closure_v2/evaluation_cohorts.yaml"),
    Path("src/experiments/closure_v2/audit_v1_inputs.py"),
    Path("src/experiments/closure_v2/contracts.py"),
    Path("tests/closure_v2/test_v1_input_audit.py"),
    Path("tests/closure_v2/test_contracts.py"),
)
ARTIFACT_PATHS = (
    "reports/closure_v2/00_protocol/development_lock.json",
    "reports/closure_v2/00_protocol/model_lock.json",
    "reports/closure_v2/00_protocol/fresh_candidate_inventory.csv",
    "reports/closure_v2/00_protocol/fresh_cohort_decision.json",
    "reports/closure_v2/00_protocol/fresh_cohort_manifest.json",
    "reports/closure_v2/00_protocol/outcome_access_log.jsonl",
    "data/closure_v2/development/fit_eligibility.parquet",
    "data/closure_v2/development/shared_fit_keys.parquet",
    "reports/closure_v2/01_surface/eligibility_manifest.json",
    "reports/closure_v2/01_surface/locked_evaluation_input_manifest.json",
    "models/closure_v2/P0",
    "models/closure_v2/P1",
    "reports/closure_v2/02_models",
    "reports/closure_v2/03_calibration/calibration_manifest.json",
    "data/closure_v2/predictions_long.parquet",
    "reports/closure_v2/04_evaluation/evaluation_manifest.json",
    "reports/closure_v2/05_inference/bootstrap_distributions.parquet",
    "data/closure_v2/degradation_masks.parquet",
    "reports/closure_v2/06_degradation/DEGRADATION_REPORT.md",
    "reports/closure_v2/07_planning/planning_origin_deltas.parquet",
    "reports/closure_v2/08_synthesis/synthesis_manifest.json",
    "reports/closure_v2/09_certification/final_certification_manifest.json",
)


def _mapping(value: Any, *, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ClosureContractError(f"{path} must be a mapping")
    return value


def _exact(mapping: Mapping[str, Any], key: str, expected: Any, *, path: str) -> None:
    if mapping.get(key) != expected:
        raise ClosureContractError(f"{path}.{key} must be {expected!r}; found {mapping.get(key)!r}")


def _file_record(relative: Path, *, role: str) -> dict[str, Any]:
    path = PROJECT_ROOT / relative
    if not path.is_file() or path.is_symlink():
        raise ClosureContractError(f"Protocol component must be a regular file: {relative}")
    return {"path": relative.as_posix(), "role": role, "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=PROJECT_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def validate_analysis_plan(path: Path = ANALYSIS_PLAN) -> dict[str, Any]:
    plan = load_yaml_mapping(path)
    validate_json_schema(plan, load_json_mapping(ANALYSIS_SCHEMA), instance_path="$.analysis_plan")
    _exact(plan, "seeds", EXPECTED_SEEDS, path="analysis_plan")
    _exact(plan, "denominators", EXPECTED_DENOMINATORS, path="analysis_plan")
    authorities = _mapping(plan["authorities"], path="analysis_plan.authorities")
    _exact(authorities, "closure_v1_certification_commit", EXPECTED_CERTIFICATION_COMMIT, path="analysis_plan.authorities")
    _exact(authorities, "closure_v1_science_commit", EXPECTED_SCIENCE_COMMIT, path="analysis_plan.authorities")
    _exact(authorities, "closure_v1_synthesis_commit", EXPECTED_SYNTHESIS_COMMIT, path="analysis_plan.authorities")
    _exact(authorities, "closure_v1_editorial_commit", EXPECTED_EDITORIAL_COMMIT, path="analysis_plan.authorities")
    _exact(authorities, "closure_v1_is_immutable", True, path="analysis_plan.authorities")
    surface = _mapping(plan["surface"], path="analysis_plan.surface")
    _exact(surface, "history_length_months", 12, path="analysis_plan.surface")
    _exact(surface, "horizons_months", [1, 2, 3], path="analysis_plan.surface")
    _exact(surface, "observed_chla_at_any_input_lag", "forbidden", path="analysis_plan.surface")
    models = _mapping(plan["models"], path="analysis_plan.models")
    _exact(models, "primary_fit_key_policy", "exact_P0_P1_shared_fit_intersection", path="analysis_plan.models")
    _exact(models, "canonical_grud_claim_authorized", False, path="analysis_plan.models")
    outcome = _mapping(plan["outcome_access"], path="analysis_plan.outcome_access")
    _exact(outcome, "before_model_lock", "forbidden", path="analysis_plan.outcome_access")
    _exact(outcome, "availability_before_model_lock", "forbidden", path="analysis_plan.outcome_access")
    inference = _mapping(plan["inference"], path="analysis_plan.inference")
    _exact(inference, "bootstrap_replicates", 2000, path="analysis_plan.inference")
    _exact(inference, "seed_pseudoreplication", "forbidden", path="analysis_plan.inference")
    return plan


def validate_eligibility_policy(path: Path = ELIGIBILITY_POLICY) -> dict[str, Any]:
    policy = load_yaml_mapping(path)
    validate_json_schema(policy, load_json_mapping(ELIGIBILITY_SCHEMA), instance_path="$.eligibility_policy")
    thresholds = _mapping(policy["authorization_thresholds"], path="eligibility_policy.authorization_thresholds")
    expected = {
        "minimum_overall_fit_eligibility_fraction": 0.90,
        "minimum_training_rows": 5000,
        "minimum_model_selection_rows": 500,
        "minimum_calibration_rows": 200,
        "minimum_training_locations": 200,
        "minimum_model_selection_locations": 50,
        "minimum_calibration_locations": 30,
    }
    if dict(thresholds) != expected:
        raise ClosureContractError("Eligibility authorization thresholds drifted")
    shared = _mapping(policy["primary_shared_fit"], path="eligibility_policy.primary_shared_fit")
    _exact(shared, "models", ["P0", "P1"], path="eligibility_policy.primary_shared_fit")
    _exact(shared, "require_identical_keys_by_seed", True, path="eligibility_policy.primary_shared_fit")
    ledger = _mapping(policy["ledger"], path="eligibility_policy.ledger")
    _exact(ledger, "retain_all_intent_rows", True, path="eligibility_policy.ledger")
    _exact(ledger, "incomplete_rows_in_loss", False, path="eligibility_policy.ledger")
    return policy


def validate_evaluation_cohorts() -> dict[str, Any]:
    cohorts = load_yaml_mapping("configs/closure_v2/evaluation_cohorts.yaml")
    _exact(cohorts, "decision_order", ["fresh_location", "forward_temporal", "external", "insufficient_support"], path="evaluation_cohorts")
    fresh = _mapping(cohorts["fresh_location"], path="evaluation_cohorts.fresh_location")
    _exact(fresh, "minimum_new_locations", 40, path="evaluation_cohorts.fresh_location")
    _exact(fresh, "minimum_intent_origins_per_horizon", 500, path="evaluation_cohorts.fresh_location")
    audit = _mapping(fresh["prelock_input_only_feasibility_audit"], path="evaluation_cohorts.fresh_location.prelock_input_only_feasibility_audit")
    if int(audit["candidate_location_count"]) < 40 or int(audit["intent_origins_per_horizon"]) < 500:
        raise ClosureContractError("The input-only fresh-location feasibility audit does not pass")
    _exact(audit, "chla_columns_read", False, path="evaluation_cohorts.fresh_location.prelock_input_only_feasibility_audit")
    _exact(audit, "target_paths_opened", False, path="evaluation_cohorts.fresh_location.prelock_input_only_feasibility_audit")
    _exact(audit, "target_availability_inspected", False, path="evaluation_cohorts.fresh_location.prelock_input_only_feasibility_audit")
    return cohorts


def validate_protocol() -> dict[str, Any]:
    v1_audit = audit_repository(PROJECT_ROOT)
    plan = validate_analysis_plan()
    policy = validate_eligibility_policy()
    cohorts = validate_evaluation_cohorts()
    benchmark = load_yaml_mapping("configs/closure_v2/model_benchmark.yaml")
    _exact(benchmark, "primary_comparisons", ["P1_vs_B2", "P1_vs_P0"], path="model_benchmark")
    _exact(benchmark, "unavailable_model_replacement", "forbidden", path="model_benchmark")
    if protected := v1_audit["protected_v1_changes"]:
        raise ClosureContractError(f"Closure V1 drift detected: {protected}")
    return {"v1_audit": v1_audit, "analysis_plan": plan, "eligibility_policy": policy, "evaluation_cohorts": cohorts, "model_benchmark": benchmark}


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_exclusive(relative: Path, content: bytes) -> None:
    destination = PROJECT_ROOT / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.is_file() and not destination.is_symlink() and destination.read_bytes() == content:
            return
        raise ClosureContractError(f"Refusing to overwrite protocol output: {relative}")
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _inventory_bytes() -> bytes:
    rows = [(path, "planned") for path in ARTIFACT_PATHS]
    lines = ["artifact_path,status\n"]
    lines.extend(f"{path},{status}\n" for path, status in rows)
    return "".join(lines).encode("utf-8")


def _replace_manifest_last(relative: Path, content: bytes) -> None:
    destination = PROJECT_ROOT / relative
    if destination.is_symlink() or not destination.is_file():
        raise ClosureContractError(f"Completion manifest must be a regular file: {relative}")
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _finalize_reference_manifest() -> None:
    manifest = load_json_mapping(REFERENCE_MANIFEST)
    manifest["status"] = "completed"
    manifest["outputs"] = [_file_record(path, role="phase_0_or_protocol_output") for path in PROTOCOL_REPORT_OUTPUTS]
    manifest["script"] = _file_record(Path("src/experiments/closure_v2/contracts.py"), role="completion_manifest_writer")
    manifest["inputs"] = [
        _file_record(ANALYSIS_PLAN, role="analysis_plan"),
        _file_record(ELIGIBILITY_POLICY, role="eligibility_policy"),
    ]
    manifest["protocol_lock_path"] = PROTOCOL_LOCK.as_posix()
    manifest["manifest_written_last"] = True
    _replace_manifest_last(REFERENCE_MANIFEST, _canonical_json(manifest))


def write_protocol_lock() -> dict[str, Any]:
    validated = validate_protocol()
    inventory_bytes = _inventory_bytes()
    _write_exclusive(ARTIFACT_INVENTORY, inventory_bytes)
    component_records = [_file_record(path, role="protocol_component") for path in PROTOCOL_COMPONENTS]
    component_digest = hashlib.sha256(_canonical_json({"components": component_records})).hexdigest()
    inventory_record = _file_record(ARTIFACT_INVENTORY, role="artifact_inventory")
    v1 = validated["v1_audit"]
    payload = {
        "schema_version": "closure_v2_protocol_lock_v1",
        "experiment_id": "closure_v2",
        "status": "locked_unpublished",
        "base_head": _git("rev-parse", "HEAD"),
        "branch": _git("branch", "--show-current"),
        "v1_tag_object": EXPECTED_TAG_OBJECT,
        "v1_peeled_commit": EXPECTED_CERTIFICATION_COMMIT,
        "v1_inventory_digest_sha256": v1["inventory_digest_sha256"],
        "components": component_records,
        "component_digest_sha256": component_digest,
        "artifact_inventory": inventory_record,
        "fresh_primary_prelock_feasibility": {"route": "fresh_location", "locations": 137, "intent_origins_per_horizon": 2286, "input_only": True, "authoritative_selection_deferred_until_after_model_lock": True},
        "fit_authorized": False,
        "outcome_access_authorized": False,
        "evaluation_authorized": False,
        "parquet_files_opened_by_protocol_locker": False,
        "dvc_commands_executed_by_protocol_locker": False,
        "completion_manifest": REFERENCE_MANIFEST.as_posix(),
        "manifest_written_last": True,
    }
    _write_exclusive(PROTOCOL_LOCK, _canonical_json(payload))
    _finalize_reference_manifest()
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate", type=Path, default=ANALYSIS_PLAN)
    parser.add_argument("--write-lock", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.validate != ANALYSIS_PLAN:
        validate_analysis_plan(args.validate)
        result: Mapping[str, Any] = {"status": "passed", "validated": args.validate.as_posix()}
    elif args.write_lock:
        lock = write_protocol_lock()
        result = {"status": lock["status"], "component_count": len(lock["components"]), "component_digest_sha256": lock["component_digest_sha256"], "lock_path": PROTOCOL_LOCK.as_posix()}
    else:
        validate_protocol()
        result = {"status": "ready_to_lock", "validated": ANALYSIS_PLAN.as_posix(), "parquet_files_opened": False, "dvc_commands_executed": False}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
