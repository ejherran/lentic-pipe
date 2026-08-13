#!/usr/bin/env python
"""Run the single sealed Closure V1 evaluation batch.

The executable is published before formal E0-M.  Import and ``--check-only``
are outcome-free and write-free.  ``--execute-sealed-batch`` delegates its
first operation to the future effective E0-U authority; while that authority
does not exist, execution fails before resolving or opening any outcome path.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType, ModuleType
from typing import Any, Mapping, Sequence, cast


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = Path("src/experiments/run_closure_benchmark.py")
FORMAL_MODEL_LOCK_GATE = "E0-M"
UNBLINDING_GATE = "E0-U"
GATE = FORMAL_MODEL_LOCK_GATE
PATCH_GATE = FORMAL_MODEL_LOCK_GATE
SEALED_BATCH_MODE = "--execute-sealed-batch"
CHECK_ONLY_MODE = "--check-only"
SEALED_BATCH_ARGV = (
    ".venv/bin/python",
    "-I",
    "-B",
    SCRIPT_PATH.as_posix(),
    SEALED_BATCH_MODE,
)
SEALED_BATCH_COMMAND_ARGV = SEALED_BATCH_ARGV
SEALED_BATCH_COMMAND = " ".join(SEALED_BATCH_ARGV) + "\n"
E0_U_AUTHORITY_MODULE = "src.experiments.closure_e0_u_authority"
E0_U_AUTHORITY_API = "require_closure_e0_u_authority"
E0_U_AUTHORITY_PATH = Path("src/experiments/closure_e0_u_authority.py")
INTERNAL_E1_EXECUTOR_API = "_execute_e1_locked_benchmark_stage"

OUTCOME_ACCESS_LOG_PATH = Path(
    "reports/closure_v1/00_protocol/outcome_access_log.jsonl"
)
LOCKED_INPUT_MANIFEST_PATH = Path(
    "reports/closure_v1/01_surface/locked_evaluation_input_manifest.json"
)
FINAL_CALIBRATION_MANIFEST_PATH = Path(
    "reports/closure_v1/03_calibration/final_calibration_manifest.json"
)
MODEL_LOCK_PATH = Path("reports/closure_v1/00_protocol/model_lock.yaml")
CALIBRATION_LOCK_PATH = Path("reports/closure_v1/00_protocol/calibration_lock.yaml")
HYPOTHESIS_REGISTRY_PATH = Path(
    "reports/closure_v1/00_protocol/hypothesis_registry.csv"
)
LOCKED_BATCH_COMMAND_PATH = Path(
    "reports/closure_v1/00_protocol/locked_batch_command.txt"
)

MODEL_IDS = ("B0", "B1", "B2", "F0", "F1", "P0", "P1", "M0", "A0", "A1", "A2")
HORIZONS_MONTHS = (1, 2, 3)
REGISTERED_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
TERMINAL_STATUSES = (
    "success",
    "input_ineligible",
    "target_unavailable",
    "model_unavailable",
    "numerical_failure",
    "infrastructure_failure",
)


class ClosureBenchmarkError(RuntimeError):
    """Fail-closed error for the sealed Closure V1 batch."""


@dataclass(frozen=True)
class BatchStage:
    stage_id: str
    role: str
    requires_outcomes: bool
    output_root: str
    output_paths: tuple[str, ...]


@dataclass(frozen=True)
class BatchComponent:
    component_id: str
    stage_id: str
    module_name: str
    source_path: str
    preflight_api: str
    execute_api: str


BATCH_STAGES = (
    BatchStage(
        "E0-U",
        "authorize_and_log_single_opening",
        False,
        "reports/closure_v1/00_protocol",
        (OUTCOME_ACCESS_LOG_PATH.as_posix(),),
    ),
    BatchStage(
        "E1",
        "paired_final_benchmark",
        True,
        "reports/closure_v1/01_benchmark",
        (
            "reports/closure_v1/01_benchmark/model_metrics_long.csv",
            "reports/closure_v1/01_benchmark/model_comparison_paired.csv",
            "reports/closure_v1/01_benchmark/benchmark_report.md",
            "reports/closure_v1/01_benchmark/benchmark_manifest.json",
            "data/closure_v1/predictions_long.parquet",
        ),
    ),
    BatchStage(
        "E2",
        "locked_internal_location_holdout",
        True,
        "reports/closure_v1/02_site_transfer",
        (
            "reports/closure_v1/02_site_transfer/location_holdout_metrics.csv",
            "reports/closure_v1/02_site_transfer/site_level_metrics.csv",
            "reports/closure_v1/02_site_transfer/fold_assignments.csv",
            "reports/closure_v1/02_site_transfer/generalization_gap.csv",
            "reports/closure_v1/02_site_transfer/site_transfer_report.md",
        ),
    ),
    BatchStage(
        "E3",
        "bloom_threshold_sensitivity",
        True,
        "reports/closure_v1/03_thresholds",
        (
            "reports/closure_v1/03_thresholds/threshold_prevalence.csv",
            "reports/closure_v1/03_thresholds/threshold_metrics.csv",
            "reports/closure_v1/03_thresholds/threshold_pairwise_differences.csv",
            "reports/closure_v1/03_thresholds/rank_stability.csv",
            "reports/closure_v1/03_thresholds/threshold_sensitivity_report.md",
        ),
    ),
    BatchStage(
        "E4",
        "direct_trophic_state_validation",
        True,
        "reports/closure_v1/04_trophic",
        (
            "reports/closure_v1/04_trophic/trophic_proxy_metrics.csv",
            "reports/closure_v1/04_trophic/carlson_reference_metrics.csv",
            "reports/closure_v1/04_trophic/trophic_confusion_matrices.csv",
            "reports/closure_v1/04_trophic/nla_semantic_metrics.csv",
            "reports/closure_v1/04_trophic/trophic_validation_report.md",
        ),
    ),
    BatchStage(
        "E5",
        "paired_hierarchical_inference",
        True,
        "reports/closure_v1/05_inference",
        (
            "reports/closure_v1/05_inference/pairwise_effects.csv",
            "reports/closure_v1/05_inference/site_level_losses.csv",
            "reports/closure_v1/05_inference/bootstrap_distributions.parquet",
            "reports/closure_v1/05_inference/multiplicity_report.csv",
            "reports/closure_v1/05_inference/statistical_inference_report.md",
        ),
    ),
    BatchStage(
        "E6",
        "matched_pipe_mifal_degradation",
        True,
        "reports/closure_v1/06_degradation",
        (
            "data/closure_v1/degradation_masks.parquet",
            "reports/closure_v1/06_degradation/matched_degradation_metrics.csv",
            "reports/closure_v1/06_degradation/matched_degradation_pairwise.csv",
            "reports/closure_v1/06_degradation/failure_registry.csv",
            "reports/closure_v1/06_degradation/robustness_auc.csv",
            "reports/closure_v1/06_degradation/matched_degradation_report.md",
        ),
    ),
    BatchStage(
        "E7",
        "locked_anfis_ablation_evaluation",
        True,
        "reports/closure_v1/07_anfis_ablation",
        (
            "reports/closure_v1/07_anfis_ablation/ablation_metrics.csv",
            "reports/closure_v1/07_anfis_ablation/ablation_pairwise.csv",
            "reports/closure_v1/07_anfis_ablation/membership_stability.csv",
            "reports/closure_v1/07_anfis_ablation/anfis_learning_curve.csv",
            "reports/closure_v1/07_anfis_ablation/anfis_ablation_report.md",
        ),
    ),
    BatchStage(
        "E8",
        "uncertainty_recalibration_ledger",
        True,
        "reports/closure_v1/08_uncertainty",
        (
            "reports/closure_v1/08_uncertainty/uncertainty_ledger.csv",
            "reports/closure_v1/08_uncertainty/conditional_coverage.csv",
            "reports/closure_v1/08_uncertainty/recalibration_comparison.csv",
            "reports/closure_v1/08_uncertainty/reliability_bins.csv",
            "reports/closure_v1/08_uncertainty/uncertainty_report.md",
        ),
    ),
    BatchStage(
        "E9",
        "counterfactual_planning_robustness",
        True,
        "reports/closure_v1/09_planning",
        (
            "reports/closure_v1/09_planning/planning_origin_deltas.parquet",
            "reports/closure_v1/09_planning/planning_bootstrap.csv",
            "reports/closure_v1/09_planning/planning_sensitivity.csv",
            "reports/closure_v1/09_planning/ecological_coherence.csv",
            "reports/closure_v1/09_planning/planning_inference_report.md",
        ),
    ),
    BatchStage(
        "E10",
        "reproducible_api_and_evidence_freeze",
        True,
        "reports/closure_v1/10_api",
        (
            "reports/closure_v1/10_api/public_tests.xml",
            "reports/closure_v1/10_api/test_report.md",
            "reports/closure_v1/10_api/openapi.json",
            "reports/closure_v1/10_api/openapi_contract_report.md",
            "reports/closure_v1/10_api/end_to_end_report.md",
            "reports/closure_v1/10_api/environment.json",
        ),
    ),
)

COMPONENT_PREFLIGHT_API = "preflight_closure_sealed_batch_component"
COMPONENT_EXECUTE_API = "execute_closure_sealed_batch_component"
BATCH_COMPONENTS = (
    BatchComponent(
        "E2_site_transfer",
        "E2",
        "src.experiments.evaluate_site_transfer",
        "src/experiments/evaluate_site_transfer.py",
        COMPONENT_PREFLIGHT_API,
        COMPONENT_EXECUTE_API,
    ),
    BatchComponent(
        "E3_threshold_sensitivity",
        "E3",
        "src.experiments.evaluate_threshold_sensitivity",
        "src/experiments/evaluate_threshold_sensitivity.py",
        COMPONENT_PREFLIGHT_API,
        COMPONENT_EXECUTE_API,
    ),
    BatchComponent(
        "E4_reference_targets",
        "E4",
        "src.experiments.build_trophic_reference_targets",
        "src/experiments/build_trophic_reference_targets.py",
        COMPONENT_PREFLIGHT_API,
        COMPONENT_EXECUTE_API,
    ),
    BatchComponent(
        "E4_trophic_evaluation",
        "E4",
        "src.experiments.evaluate_trophic_state",
        "src/experiments/evaluate_trophic_state.py",
        COMPONENT_PREFLIGHT_API,
        COMPONENT_EXECUTE_API,
    ),
    BatchComponent(
        "E5_clustered_inference",
        "E5",
        "src.experiments.compare_models_clustered",
        "src/experiments/compare_models_clustered.py",
        COMPONENT_PREFLIGHT_API,
        COMPONENT_EXECUTE_API,
    ),
    BatchComponent(
        "E6_matched_degradation",
        "E6",
        "src.experiments.evaluate_matched_degradation",
        "src/experiments/evaluate_matched_degradation.py",
        COMPONENT_PREFLIGHT_API,
        COMPONENT_EXECUTE_API,
    ),
    BatchComponent(
        "E7_anfis_ablation",
        "E7",
        "src.experiments.evaluate_anfis_ablation",
        "src/experiments/evaluate_anfis_ablation.py",
        COMPONENT_PREFLIGHT_API,
        COMPONENT_EXECUTE_API,
    ),
    BatchComponent(
        "E8_uncertainty",
        "E8",
        "src.experiments.calibrate_uncertainty_closure",
        "src/experiments/calibrate_uncertainty_closure.py",
        COMPONENT_PREFLIGHT_API,
        COMPONENT_EXECUTE_API,
    ),
    BatchComponent(
        "E9_planning_inference",
        "E9",
        "src.experiments.evaluate_planning_inference",
        "src/experiments/evaluate_planning_inference.py",
        COMPONENT_PREFLIGHT_API,
        COMPONENT_EXECUTE_API,
    ),
    BatchComponent(
        "E10_evidence_matrix",
        "E10",
        "src.reporting.build_closure_evidence_matrix",
        "src/reporting/build_closure_evidence_matrix.py",
        COMPONENT_PREFLIGHT_API,
        COMPONENT_EXECUTE_API,
    ),
)

CURRENT_MODEL_AVAILABILITY = MappingProxyType(
    {
        "B0": "available",
        "B1": "available",
        "B2": "available",
        "F0": "available",
        "F1": "available",
        "P0": "unavailable",
        "P1": "unavailable",
        "M0": "available",
        "A0": "available",
        "A1": "available",
        "A2": "unavailable",
    }
)

BATCH_CONTRACT = MappingProxyType(
    {
        "schema_version": "closure_sealed_evaluation_batch_v1",
        "experiment_id": "closure_v1",
        "formal_model_lock_gate": FORMAL_MODEL_LOCK_GATE,
        "execution_gate": UNBLINDING_GATE,
        "sealed_argv": list(SEALED_BATCH_ARGV),
        "sealed_command": SEALED_BATCH_COMMAND,
        "authority_is_first_execute_operation": True,
        "evaluation_refit": "forbidden",
        "failed_model_replacement": "forbidden",
        "silent_row_deletion": "forbidden",
        "manifest_last": True,
        "one_batch_only": True,
        "registered_seeds": list(REGISTERED_SEEDS),
        "horizons_months": list(HORIZONS_MONTHS),
        "model_ids": list(MODEL_IDS),
        "model_availability": dict(CURRENT_MODEL_AVAILABILITY),
        "terminal_statuses": list(TERMINAL_STATUSES),
        "stages": [
            {
                "stage_id": stage.stage_id,
                "role": stage.role,
                "requires_outcomes": stage.requires_outcomes,
                "output_root": stage.output_root,
                "output_paths": list(stage.output_paths),
            }
            for stage in BATCH_STAGES
        ],
        "components": [
            {
                "component_id": component.component_id,
                "stage_id": component.stage_id,
                "module_name": component.module_name,
                "source_path": component.source_path,
                "preflight_api": component.preflight_api,
                "execute_api": component.execute_api,
            }
            for component in BATCH_COMPONENTS
        ],
        "e1_scientific_executor_status": "not_implemented",
    }
)


def _canonical_json_bytes(value: Any) -> bytes:
    if isinstance(value, MappingProxyType):
        value = dict(value)
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sealed_batch_contract() -> dict[str, Any]:
    """Return the public, mutation-free batch contract used by E0-M."""

    return cast(dict[str, Any], json.loads(_canonical_json_bytes(BATCH_CONTRACT)))


def sealed_batch_contract_sha256() -> str:
    return _sha256_bytes(_canonical_json_bytes(BATCH_CONTRACT))


def validate_sealed_batch_contract(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = sealed_batch_contract()
    if dict(value) != expected:
        raise ClosureBenchmarkError("E0-M sealed batch contract drifted")
    return expected


def validate_sealed_batch_command(value: str | bytes) -> str:
    """Accept only the exact newline-terminated, non-shell batch command."""

    try:
        text = value.decode("utf-8") if isinstance(value, bytes) else value
    except UnicodeDecodeError as exc:
        raise ClosureBenchmarkError("E0-M sealed batch command is not UTF-8") from exc
    if type(text) is not str or text != SEALED_BATCH_COMMAND:
        raise ClosureBenchmarkError("E0-M sealed batch command drifted")
    return text


def _read_regular_source(
    relative_path: Path, *, repo_root: Path
) -> tuple[bytes, os.stat_result]:
    path = repo_root / relative_path
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        metadata = os.fstat(descriptor)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        payload = b"".join(chunks)
        after = os.fstat(descriptor)
        named = path.lstat()
    except OSError as exc:
        raise ClosureBenchmarkError(
            f"E0-M source cannot be read: {relative_path.as_posix()}"
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o644
        or (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_mode,
            metadata.st_nlink,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
        )
        != (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        or (metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_nlink)
        != (named.st_dev, named.st_ino, named.st_mode, named.st_nlink)
        or len(payload) != metadata.st_size
    ):
        raise ClosureBenchmarkError(
            f"E0-M source identity drifted: {relative_path.as_posix()}"
        )
    return payload, metadata


def runner_source_record(*, repo_root: Path | None = None) -> dict[str, Any]:
    """Return the source record that the formal E0-M lock must seal."""

    root = PROJECT_ROOT if repo_root is None else Path(repo_root).resolve()
    payload, metadata = _read_regular_source(SCRIPT_PATH, repo_root=root)
    return {
        "path": SCRIPT_PATH.as_posix(),
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "mode": stat.S_IMODE(metadata.st_mode),
        "nlink": int(metadata.st_nlink),
        "contract_sha256": sealed_batch_contract_sha256(),
        "sealed_command": SEALED_BATCH_COMMAND,
    }


def validate_runner_source_record(
    record: Mapping[str, Any], *, repo_root: Path | None = None
) -> dict[str, Any]:
    observed = runner_source_record(repo_root=repo_root)
    if dict(record) != observed:
        raise ClosureBenchmarkError("E0-M batch runner source record drifted")
    return observed


def _component_source_record(
    component: BatchComponent, *, repo_root: Path
) -> dict[str, Any]:
    relative_path = Path(component.source_path)
    try:
        payload, metadata = _read_regular_source(relative_path, repo_root=repo_root)
        decoded = payload.decode("utf-8")
        tree = ast.parse(decoded, filename=component.source_path)
    except (ClosureBenchmarkError, UnicodeDecodeError, SyntaxError) as exc:
        return {
            "component_id": component.component_id,
            "stage_id": component.stage_id,
            "source_path": component.source_path,
            "status": "missing_or_invalid",
            "reason": type(exc).__name__,
        }
    functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing_apis = sorted(
        {component.preflight_api, component.execute_api}.difference(functions)
    )
    return {
        "component_id": component.component_id,
        "stage_id": component.stage_id,
        "module_name": component.module_name,
        "source_path": component.source_path,
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "mode": stat.S_IMODE(metadata.st_mode),
        "nlink": int(metadata.st_nlink),
        "required_apis": [component.preflight_api, component.execute_api],
        "missing_apis": missing_apis,
        "status": "ready" if not missing_apis else "missing_required_api",
    }


def collect_sealed_batch_component_readiness(
    *, repo_root: Path | None = None
) -> dict[str, Any]:
    """Inspect source contracts only; never import a scientific component."""

    root = PROJECT_ROOT if repo_root is None else Path(repo_root).resolve()
    records = [
        _component_source_record(component, repo_root=root)
        for component in BATCH_COMPONENTS
    ]
    missing = [
        {
            "component_id": "E1_benchmark_scientific_executor",
            "stage_id": "E1",
            "reason": f"missing internal API {INTERNAL_E1_EXECUTOR_API}",
        }
    ]
    missing.extend(
        {
            "component_id": record["component_id"],
            "stage_id": record["stage_id"],
            "reason": record["status"],
        }
        for record in records
        if record["status"] != "ready"
    )
    return {
        "status": (
            "sealed_batch_components_ready"
            if not missing
            else "sealed_batch_components_incomplete"
        ),
        "component_count": 1 + len(BATCH_COMPONENTS),
        "external_component_count": len(BATCH_COMPONENTS),
        "ready_external_component_count": sum(
            record["status"] == "ready" for record in records
        ),
        "missing_component_count": len(missing),
        "missing_components": missing,
        "component_source_records": records,
        "outcome_paths_opened": False,
        "future_outcomes_accessed": False,
        "writes_performed": False,
    }


def _load_e0_u_authority_module() -> ModuleType:
    # ``-I`` intentionally omits the repository root from ``sys.path``.  Add
    # only this exact root immediately before importing the sealed authority;
    # no scientific component is resolved at this boundary.
    root_text = PROJECT_ROOT.as_posix()
    if not sys.path or sys.path[0] != root_text:
        sys.path.insert(0, root_text)
    try:
        return importlib.import_module(E0_U_AUTHORITY_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name == E0_U_AUTHORITY_MODULE:
            raise ClosureBenchmarkError(
                "E0-U authority is not published; sealed batch execution is forbidden"
            ) from exc
        raise ClosureBenchmarkError("E0-U authority import failed closed") from exc
    except BaseException as exc:
        raise ClosureBenchmarkError("E0-U authority import failed closed") from exc


def _require_e0_u_authority_first() -> dict[str, Any]:
    """Perform the mandatory first sealed-execution operation."""

    module = _load_e0_u_authority_module()
    require = getattr(module, E0_U_AUTHORITY_API, None)
    if not callable(require):
        raise ClosureBenchmarkError("E0-U authority API is absent")
    try:
        raw = require(verify_remote=True, repo_root=PROJECT_ROOT)
    except BaseException as exc:
        raise ClosureBenchmarkError("E0-U authority rejected sealed execution") from exc
    if not isinstance(raw, Mapping):
        raise ClosureBenchmarkError("E0-U authority result is not a mapping")
    authority = dict(raw)
    expected = {
        "gate": UNBLINDING_GATE,
        "effective_authority": True,
        "sealed_batch_execution_authorized": True,
        "e0_m_authorized": True,
        "e0_u_authorized": True,
        "evaluation_authorized": True,
        "outcome_access_authorized": True,
        "writes_performed": False,
    }
    for key, value in expected.items():
        if type(authority.get(key)) is not type(value) or authority.get(key) != value:
            raise ClosureBenchmarkError(f"E0-U authority field drifted: {key}")
    if authority.get("sealed_batch_command") != SEALED_BATCH_COMMAND:
        raise ClosureBenchmarkError("E0-U authority sealed command drifted")
    return authority


def check_only(*, repo_root: Path | None = None) -> dict[str, Any]:
    """Validate the runner itself without opening outcomes or writing files."""

    root = PROJECT_ROOT if repo_root is None else Path(repo_root).resolve()
    source_before = runner_source_record(repo_root=root)
    validate_sealed_batch_command(SEALED_BATCH_COMMAND)
    readiness = collect_sealed_batch_component_readiness(repo_root=root)
    source_after = runner_source_record(repo_root=root)
    if source_after != source_before:
        raise ClosureBenchmarkError("E0-M batch runner changed during check-only")
    execution_ready = readiness["missing_component_count"] == 0
    return {
        "gate": FORMAL_MODEL_LOCK_GATE,
        "status": (
            "sealed_batch_runner_ready_for_formal_lock"
            if execution_ready
            else "sealed_batch_runner_incomplete"
        ),
        "runner": source_before,
        "batch_contract_sha256": sealed_batch_contract_sha256(),
        "sealed_batch_command": SEALED_BATCH_COMMAND,
        "component_readiness": readiness,
        "formal_model_lock_ready": execution_ready,
        "evaluator_available": execution_ready,
        "missing_component_count": readiness["missing_component_count"],
        "sealed_batch_execution_ready": execution_ready,
        "e0_u_authority_path": E0_U_AUTHORITY_PATH.as_posix(),
        "e0_u_authority_inspected": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "evaluation_authorized": False,
        "outcome_access_authorized": False,
        "target_paths_opened": False,
        "outcome_paths_opened": False,
        "future_outcomes_accessed": False,
        "writes_performed": False,
    }


def _load_ready_components(
    readiness: Mapping[str, Any],
) -> tuple[tuple[BatchComponent, ModuleType], ...]:
    if readiness.get("status") != "sealed_batch_components_ready":
        raise ClosureBenchmarkError("E0-U component readiness drifted")
    loaded: list[tuple[BatchComponent, ModuleType]] = []
    for component in BATCH_COMPONENTS:
        try:
            module = importlib.import_module(component.module_name)
        except BaseException as exc:
            raise ClosureBenchmarkError(
                f"E0-U component import failed closed: {component.component_id}"
            ) from exc
        if not callable(getattr(module, component.preflight_api, None)) or not callable(
            getattr(module, component.execute_api, None)
        ):
            raise ClosureBenchmarkError(
                f"E0-U component API drifted: {component.component_id}"
            )
        loaded.append((component, module))
    return tuple(loaded)


def _execute_with_verified_e0_u_authority(
    authority: Mapping[str, Any],
    readiness: Mapping[str, Any],
) -> dict[str, Any]:
    # No component or outcome may be opened until the authority returned.
    components = _load_ready_components(readiness)
    preflights: list[dict[str, Any]] = []
    for component, module in components:
        preflight = getattr(module, component.preflight_api)
        try:
            raw = preflight(
                authority=dict(authority),
                sealed_batch_contract=sealed_batch_contract(),
                repo_root=PROJECT_ROOT,
            )
        except BaseException as exc:
            raise ClosureBenchmarkError(
                f"E0-U component preflight failed: {component.component_id}"
            ) from exc
        if not isinstance(raw, Mapping):
            raise ClosureBenchmarkError(
                f"E0-U component preflight is not a mapping: {component.component_id}"
            )
        result = dict(raw)
        expected = {
            "component_id": component.component_id,
            "stage_id": component.stage_id,
            "status": "ready",
            "outcome_paths_opened": False,
            "writes_performed": False,
        }
        for key, value in expected.items():
            if type(result.get(key)) is not type(value) or result.get(key) != value:
                raise ClosureBenchmarkError(
                    f"E0-U component preflight field drifted: {component.component_id}:{key}"
                )
        preflights.append(result)
    # The E1 scientific executor is deliberately not present in this H slice.
    # Readiness can therefore not reach this point until a later implementation
    # extends this runner under a new, reviewed source hash.
    raise ClosureBenchmarkError(
        "E0-U E1 scientific executor is unavailable; no outcome I/O occurred"
    )


def execute_sealed_batch() -> dict[str, Any]:
    # The E0-U authority is the first operation. It must itself perform no
    # outcome I/O; only after it returns may this runner inspect source-only
    # component readiness. Missing components still reject before outcomes.
    authority = _require_e0_u_authority_first()
    readiness = collect_sealed_batch_component_readiness(repo_root=PROJECT_ROOT)
    if readiness["missing_component_count"] != 0:
        raise ClosureBenchmarkError(
            "E0-U sealed batch components are incomplete; no outcome I/O occurred: "
            + json.dumps(
                readiness["missing_components"],
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
    return _execute_with_verified_e0_u_authority(authority, readiness)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument(CHECK_ONLY_MODE, action="store_true")
    modes.add_argument(SEALED_BATCH_MODE, action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = check_only() if args.check_only else execute_sealed_batch()
    except ClosureBenchmarkError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
