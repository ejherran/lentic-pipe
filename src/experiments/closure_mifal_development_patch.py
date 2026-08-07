#!/usr/bin/env python
"""Validate the additive Closure V1 strict-MIFAL development authority.

E0-MR authorizes one deterministic, development-only M0 surface only after an
exact H/P publication chain.  H/P may hash inputs and perform the read-only Git
remote alignment check, but cannot run MIFAL, open target/outcome values, run
DVC, calibrate, compute empirical metrics, or create any E0-M/E0-U artifact.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from src.experiments import closure_contract
from src.experiments.closure_contract import ClosureContractError, validate_json_schema
from src.mifal.ed_t2 import MIFALConfig, __version__ as MIFAL_VERSION


PROJECT_ROOT = Path(__file__).resolve().parents[2]

LOCK_VERSION = "closure_mifal_development_patch_lock_v1"
PATCH_GATE = "E0-MR"
PATCH_ID = "mifal_development_authority_patch_1"
EXPERIMENT_ID = "closure_v1"
SURFACE_ID = "closure_v1_wqp_adaptive_no_current_chla"
MODEL_ID = "M0"
PATCH_BASE_COMMIT = "aa0d2cbfac186464a8b6e17b87d71aeedaa92c95"
PATCH_BASE_PARENT = "281546abdc0296e86ed0e726ffe8bc14c62a5c14"
PUBLISHED_REF = "origin/main"

DEFAULT_RUNTIME_PATH = Path("configs/closure_v1/mifal_development_runtime.yaml")
DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/mifal_development_patch_lock.schema.json"
)
DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/mifal_development_patch_lock.json"
)
DEFAULT_PATCH_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/mifal_development_patch_lock_manifest.json"
)
LOCKER_GUARD_PATH = Path(
    "tmp/closure_v1_e0_mr_locker/mifal_development_patch_lock.guard"
)

PATCH_COMPONENT_ROLES = {
    DEFAULT_RUNTIME_PATH.as_posix(): "mifal_development_runtime",
    DEFAULT_PATCH_LOCK_SCHEMA.as_posix(): "mifal_development_patch_lock_schema",
    "docs/closure_v1/E0_M_MIFAL_DEVELOPMENT_PATCH_1.md": (
        "mifal_development_patch_protocol"
    ),
    "src/experiments/closure_mifal_development_patch.py": (
        "mifal_development_patch_validator"
    ),
    "src/experiments/lock_closure_mifal_development_patch.py": (
        "mifal_development_patch_locker"
    ),
    "src/experiments/run_closure_mifal.py": "mifal_development_runner",
    "src/mifal/closure_panel_adapter.py": "mifal_strict_panel_adapter",
    "tests/test_closure_mifal_development_patch.py": (
        "mifal_development_patch_tests"
    ),
    "tests/test_run_closure_mifal.py": "mifal_development_runner_tests",
}
PATCH_PATHS = tuple(sorted(PATCH_COMPONENT_ROLES))

PHYSICAL_INPUT_ROLES = {
    "reports/closure_v1/00_protocol/protocol_lock.json": "protocol_lock",
    "reports/closure_v1/00_protocol/development_runtime_lock.json": (
        "development_runtime_lock"
    ),
    "reports/closure_v1/00_protocol/development_runtime_temporal_validation_dialect_patch_lock.json": (
        "effective_development_runtime_lock"
    ),
    "reports/closure_v1/00_protocol/development_runtime_temporal_validation_dialect_patch_lock_manifest.json": (
        "effective_development_runtime_lock_manifest"
    ),
    "src/experiments/closure_development_guard.py": "development_guard",
    "data/closure_v1/closure_holdout_assignment.csv": "holdout_assignment",
    "reports/closure_v1/00_protocol/holdout_manifest.json": "holdout_manifest",
    "data/closure_v1/common_origin_manifest.parquet": "common_origin",
    "data/closure_v1/common_origin_manifest.parquet.dvc": "common_origin_pointer",
    "reports/closure_v1/01_surface/common_origin_manifest.json": (
        "common_origin_manifest"
    ),
    "data/panel/panel_monthly_v0.parquet": "panel",
    "data/panel/panel_monthly_v0.parquet.dvc": "panel_pointer",
    "configs/closure_v1/model_benchmark.yaml": "model_benchmark",
    "configs/closure_v1/surface_primary.yaml": "primary_surface",
    "configs/closure_v1/analysis_plan.yaml": "analysis_plan",
    "configs/closure_v1/experimental_matrix.yaml": "experimental_matrix",
    "src/mifal/ed_t2.py": "mifal_core",
    "pyproject.toml": "pyproject",
    "poetry.lock": "poetry_lock",
    "reports/closure_v1/02_models/baselines/manifest.json": (
        "upstream_baseline_manifest"
    ),
    "reports/closure_v1/00_protocol/baseline_development_publication_guard_patch_lock.json": (
        "upstream_baseline_patch_lock"
    ),
    "reports/closure_v1/00_protocol/baseline_development_publication_guard_patch_lock_manifest.json": (
        "upstream_baseline_patch_lock_manifest"
    ),
    "models.dvc": "models_dvc_observer",
}
PHYSICAL_INPUT_PATHS = tuple(PHYSICAL_INPUT_ROLES)
EXPECTED_RUNTIME_PHYSICAL_INPUT_COUNT = 23
EXPECTED_COMPANION_INPUT_COUNT = 32

PANEL_PROJECTION = (
    "source_id",
    "site_id",
    "year_month",
    "mean_temperature_C",
    "n_obs_temperature_C",
    "qc_ok_rate_temperature_C",
    "std_temperature_C",
    "mean_TP_ugL",
    "n_obs_TP_ugL",
    "qc_ok_rate_TP_ugL",
    "std_TP_ugL",
    "mean_TN_ugL",
    "n_obs_TN_ugL",
    "qc_ok_rate_TN_ugL",
    "std_TN_ugL",
    "mean_secchi_depth_m",
    "n_obs_secchi_depth_m",
    "qc_ok_rate_secchi_depth_m",
    "std_secchi_depth_m",
    "mean_turbidity_NTU",
    "n_obs_turbidity_NTU",
    "qc_ok_rate_turbidity_NTU",
    "std_turbidity_NTU",
    "mean_DO_mgL",
    "n_obs_DO_mgL",
    "qc_ok_rate_DO_mgL",
    "std_DO_mgL",
)
VARIABLE_ORDER = ("Tw", "TP", "TN", "Secchi", "Turb", "DOb")
EVIDENCE_GROUPS = {
    "temperature": ["Tw"],
    "nutrients": ["TP", "TN"],
    "light": ["Secchi", "Turb"],
    "internal_do": ["DOb"],
}

RAW_PREDICTION_COLUMNS = (
    "surface_id",
    "model_id",
    "source_id",
    "site_id",
    "common_origin_id",
    "evaluation_unit_id",
    "holdout_group_id",
    "assignment_role",
    "time_role",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
    "technical_seed",
    "model_seed",
    "upstream_state_seed",
    "candidate",
    "selected_family",
    "availability_status",
    "failure_reason",
    "score_semantics",
    "raw_score",
    "predicted_bloom_probability",
    "interval_lower",
    "interval_upper",
    "data_reliability",
    "evidence_group_count",
    "payload_variable_count",
    "payload_variables",
)
RAW_STRING_COLUMNS = {
    *RAW_PREDICTION_COLUMNS[:11],
    "candidate",
    "availability_status",
    "failure_reason",
    "score_semantics",
    "payload_variables",
}
RAW_NULLABLE_COLUMNS = {
    "model_seed",
    "upstream_state_seed",
    "raw_score",
    "predicted_bloom_probability",
    "interval_lower",
    "interval_upper",
    "data_reliability",
}
RAW_CANONICAL_KEY_COLUMNS = (
    "source_id",
    "site_id",
    "origin_year_month",
    "horizon_months",
    "target_year_month",
    "common_origin_id",
    "evaluation_unit_id",
)

MIFAL_FINAL_PATHS = (
    "data/closure_v1/development/mifal/M0/raw_scores.parquet",
    "reports/closure_v1/02_models/M0/model_spec.json",
    "reports/closure_v1/02_models/M0/lineage_audit.json",
    "reports/closure_v1/02_models/M0/availability.csv",
    "reports/closure_v1/02_models/M0/report.md",
    "reports/closure_v1/02_models/M0/manifest.json",
)
MIFAL_POINTER_PATH = "data/closure_v1/development/mifal/M0/raw_scores.parquet.dvc"
MIFAL_OUTPUT_GUARD = "tmp/closure_v1_mifal_development/mifal_bundle.guard"

E0_M_PATHS = (
    "reports/closure_v1/00_protocol/model_lock.yaml",
    "reports/closure_v1/00_protocol/calibration_lock.yaml",
    "reports/closure_v1/00_protocol/hypothesis_registry.csv",
    "reports/closure_v1/00_protocol/locked_batch_command.txt",
)
OUTCOME_ACCESS_LOG = "reports/closure_v1/00_protocol/outcome_access_log.jsonl"

TYPE_CHECK_COMMAND = (".venv/bin/ty", "check")
FOCUSED_TEST_COMMAND = (
    ".venv/bin/pytest",
    "tests/test_closure_mifal_development_patch.py",
    "tests/test_run_closure_mifal.py",
    "-q",
)
# Frozen by the integrator after exact collection of the two focused files.
FOCUSED_TEST_COUNT = 62
POETRY_CHECK_COMMAND = ("poetry", "check")
PUBLICATION_GUARD_COMMAND = ("scripts/check_repo_publication_ready.sh",)
DIFF_CHECK_COMMAND = ("git", "diff", "--check")

UNPUBLISHED_AUTHORIZATIONS = {
    "strict_adapter_authorized": False,
    "mifal_one_shot_authorized": False,
    "m0_execution_authorized": False,
    "tuning_authorized": False,
    "target_access_authorized": False,
    "calibration_authorized": False,
    "metrics_authorized": False,
    "e0_m_authorized": False,
    "evaluation_authorized": False,
    "e0_u_authorized": False,
    "dvc_commands_authorized": False,
    "scientific_network_authorized": False,
    "outcome_access_authorized": False,
    "future_outcomes_accessed": False,
    "effective_in_payload": False,
    "publication_required": True,
}
EFFECTIVE_AUTHORIZATIONS = {
    "strict_adapter_authorized": True,
    "mifal_one_shot_authorized": True,
    "m0_execution_authorized": True,
    "tuning_authorized": False,
    "target_access_authorized": False,
    "calibration_authorized": False,
    "metrics_authorized": False,
    "e0_m_authorized": False,
    "evaluation_authorized": False,
    "e0_u_authorized": False,
    "dvc_commands_authorized": False,
    "scientific_network_authorized": False,
    "outcome_access_authorized": False,
    "future_outcomes_accessed": False,
}
PATCH_SEALS = {
    "h_scope_exact_nine_additions": True,
    "p_scope_exact_two_additions": True,
    "legacy_mifal_adapter_unchanged_no_direct_import_invocation_or_projection": True,
    "strict_panel_projection_twenty_seven_locked": True,
    "minimum_two_ecological_groups_locked": True,
    "raw_twenty_eight_columns_locked": True,
    "single_deterministic_surface_locked": True,
    "mifal_v5_defaults_without_tuning_locked": True,
    "structural_memory_is_global_prior_not_observation": True,
    "predicted_probability_null_before_calibration": True,
    "target_artifacts_not_inputs": True,
    "target_columns_not_scanned": True,
    "exact_six_outputs_absent_at_lock": True,
    "manifest_written_last": True,
    "companion_script_record_locked": True,
    "companion_exact_thirty_two_inputs_locked": True,
    "no_clobber_and_owned_inode_rollback_locked": True,
    "dvc_closed": True,
    "e0_m_absent": True,
    "outcome_access_log_absent": True,
    "future_outcomes_accessed": False,
}


class MifalDevelopmentPatchError(RuntimeError):
    """Raised when E0-MR cannot prove its exact closed authority."""


def _root(repo_root: Path | None = None) -> Path:
    return (repo_root or PROJECT_ROOT).resolve()


def _relative(path: Path, *, repo_root: Path | None = None) -> str:
    try:
        return path.resolve().relative_to(_root(repo_root)).as_posix()
    except ValueError as exc:
        raise MifalDevelopmentPatchError(f"Path escapes repository: {path}") from exc


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _path_digest(paths: Sequence[str]) -> str:
    return _sha256_bytes("\n".join(paths).encode("utf-8"))


def _record_digest(records: Sequence[Mapping[str, Any]]) -> str:
    return _sha256_bytes(
        json.dumps(
            list(records),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    )


def _read_regular_bytes(path: Path, *, repo_root: Path | None = None) -> bytes:
    absolute = path if path.is_absolute() else _root(repo_root) / path
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(absolute, flags)
    except OSError as exc:
        raise MifalDevelopmentPatchError(
            f"Required regular file cannot be opened safely: "
            f"{_relative(absolute, repo_root=repo_root)}"
        ) from exc
    try:
        observed = os.fstat(descriptor)
        if not stat.S_ISREG(observed.st_mode):
            raise MifalDevelopmentPatchError(
                f"Required path is not regular: {_relative(absolute, repo_root=repo_root)}"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            return handle.read()
    finally:
        os.close(descriptor)


def _file_record(
    path: Path,
    *,
    role: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    payload = _read_regular_bytes(path, repo_root=repo_root)
    absolute = path if path.is_absolute() else _root(repo_root) / path
    return {
        "path": _relative(absolute, repo_root=repo_root),
        "role": role,
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
    }


def _load_regular_json(
    path: Path,
    *,
    context: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    try:
        value = json.loads(_read_regular_bytes(path, repo_root=repo_root))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise MifalDevelopmentPatchError(f"{context} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise MifalDevelopmentPatchError(f"{context} must be a JSON object")
    return value


def _keyword_occurrences(value: Any, keyword: str) -> int:
    if isinstance(value, Mapping):
        return sum(
            (1 if key == keyword else 0) + _keyword_occurrences(child, keyword)
            for key, child in value.items()
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return sum(_keyword_occurrences(child, keyword) for child in value)
    return 0


def expected_raw_prediction_contract() -> dict[str, Any]:
    columns: list[dict[str, Any]] = []
    for name in RAW_PREDICTION_COLUMNS:
        if name in RAW_STRING_COLUMNS:
            dtype = "string"
        elif name in {"horizon_months"}:
            dtype = "int16"
        elif name in {"technical_seed", "model_seed", "upstream_state_seed"}:
            dtype = "int64"
        elif name in {"evidence_group_count", "payload_variable_count"}:
            dtype = "int8"
        elif name == "selected_family":
            dtype = "bool"
        else:
            dtype = "float64"
        columns.append(
            {"name": name, "dtype": dtype, "nullable": name in RAW_NULLABLE_COLUMNS}
        )
    return {
        "columns": columns,
        "canonical_sort_keys": list(RAW_CANONICAL_KEY_COLUMNS),
        "availability_status_values": ["success", "input_ineligible"],
        "candidate_policy": "constant_mifal_ed_t2_v5_defaults",
        "selected_family_policy": "constant_false_no_selection_or_tuning",
        "success_policy": (
            "at_least_two_evidence_groups_and_finite_raw_interval_reliability_"
            "in_closed_unit_interval"
        ),
        "success_probability_policy": (
            "predicted_bloom_probability_is_null_before_common_calibration"
        ),
        "ineligible_policy": (
            "scores_interval_and_reliability_null_but_row_retained"
        ),
        "payload_variables_encoding": "comma_joined_subsequence_of_variable_order",
        "technical_seed_policy": "constant_1729",
        "model_seed_policy": "null",
        "upstream_state_seed_policy": "null",
        "execution_exception_policy": "transaction_abort_with_owned_inode_rollback",
    }


def _default_config_digest() -> tuple[int, str]:
    payload = json.dumps(
        asdict(MIFALConfig()),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return len(payload), _sha256_bytes(payload)


def preflight_mifal_development_patch_schema(
    schema_path: Path = DEFAULT_PATCH_LOCK_SCHEMA,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Validate the physical schema before guards, commands, or data reads."""
    if schema_path != DEFAULT_PATCH_LOCK_SCHEMA:
        raise MifalDevelopmentPatchError("E0-MR requires the closed default schema path")
    schema = _load_regular_json(
        schema_path,
        context="E0-MR lock schema",
        repo_root=repo_root,
    )
    minimum_count = _keyword_occurrences(schema, "minimum")
    format_count = _keyword_occurrences(schema, "format")
    if minimum_count or format_count:
        raise MifalDevelopmentPatchError(
            "E0-MR schema uses unsupported keywords: "
            f"minimum={minimum_count}, format={format_count}"
        )
    validator = getattr(closure_contract, "_assert_supported_json_schema", None)
    if not callable(validator):
        raise MifalDevelopmentPatchError(
            "Closure JSON-schema definition validator is unavailable"
        )
    try:
        validator(schema)
    except ClosureContractError as exc:
        raise MifalDevelopmentPatchError(str(exc)) from exc
    record = _file_record(
        schema_path,
        role=PATCH_COMPONENT_ROLES[schema_path.as_posix()],
        repo_root=repo_root,
    )
    return {
        "gate": PATCH_GATE,
        "schema_path": schema_path.as_posix(),
        "schema_bytes": record["bytes"],
        "schema_sha256": record["sha256"],
        "supported_subset_verified": True,
        "minimum_keyword_absent": True,
        "format_keyword_absent": True,
    }


def _require_equal(observed: Any, expected: Any, context: str) -> None:
    if observed != expected:
        raise MifalDevelopmentPatchError(f"E0-MR {context} drifted")


def _verify_runtime_physical_pins(
    runtime: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> list[dict[str, Any]]:
    authority = runtime.get("authority")
    if not isinstance(authority, Mapping):
        raise MifalDevelopmentPatchError("E0-MR runtime authority is absent")
    raw_records = authority.get("physical_inputs")
    if not isinstance(raw_records, list):
        raise MifalDevelopmentPatchError("E0-MR physical pin list is absent")
    if authority.get("physical_input_count") != EXPECTED_RUNTIME_PHYSICAL_INPUT_COUNT:
        raise MifalDevelopmentPatchError("E0-MR physical pin count drifted")
    if len(raw_records) != EXPECTED_RUNTIME_PHYSICAL_INPUT_COUNT:
        raise MifalDevelopmentPatchError("E0-MR physical pin list length drifted")
    paths = [record.get("path") for record in raw_records if isinstance(record, Mapping)]
    if tuple(paths) != PHYSICAL_INPUT_PATHS or len(set(paths)) != len(paths):
        raise MifalDevelopmentPatchError("E0-MR physical pin paths/order drifted")
    observed_records: list[dict[str, Any]] = []
    for raw_record in raw_records:
        if not isinstance(raw_record, Mapping) or set(raw_record) != {
            "role",
            "path",
            "bytes",
            "sha256",
        }:
            raise MifalDevelopmentPatchError("E0-MR physical pin dialect drifted")
        path = str(raw_record["path"])
        expected_role = PHYSICAL_INPUT_ROLES.get(path)
        if raw_record.get("role") != expected_role:
            raise MifalDevelopmentPatchError(f"E0-MR physical pin role drifted: {path}")
        observed = _file_record(
            Path(path),
            role=str(expected_role),
            repo_root=repo_root,
        )
        if dict(raw_record) != observed:
            raise MifalDevelopmentPatchError(f"E0-MR physical pin drifted: {path}")
        observed_records.append(observed)
    return observed_records


def load_and_validate_mifal_development_runtime(
    runtime_path: Path = DEFAULT_RUNTIME_PATH,
    *,
    repo_root: Path | None = None,
    verify_physical_pins: bool = True,
) -> dict[str, Any]:
    """Load the additive runtime and enforce its scientific/operational seals."""
    if runtime_path != DEFAULT_RUNTIME_PATH:
        raise MifalDevelopmentPatchError("E0-MR requires the closed default runtime path")
    try:
        value = yaml.safe_load(_read_regular_bytes(runtime_path, repo_root=repo_root))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise MifalDevelopmentPatchError("E0-MR runtime is not valid YAML") from exc
    if not isinstance(value, dict):
        raise MifalDevelopmentPatchError("E0-MR runtime must be a mapping")

    _require_equal(
        {key: value.get(key) for key in (
            "schema_version", "experiment_id", "surface_id", "model_id",
            "status", "gate", "patch_id", "patch_base_commit",
        )},
        {
            "schema_version": "closure_mifal_development_runtime_v1",
            "experiment_id": EXPERIMENT_ID,
            "surface_id": SURFACE_ID,
            "model_id": MODEL_ID,
            "status": "ready_to_lock",
            "gate": PATCH_GATE,
            "patch_id": PATCH_ID,
            "patch_base_commit": PATCH_BASE_COMMIT,
        },
        "runtime identity",
    )
    _require_equal(set(value), {
        "schema_version", "experiment_id", "surface_id", "model_id", "status",
        "gate", "patch_id", "patch_base_commit", "authority", "patch_scope",
        "roles", "denominators", "strict_adapter", "model", "outputs",
        "reproducibility", "dvc", "authorizations",
    }, "runtime top-level keys")

    authority = value.get("authority")
    if not isinstance(authority, Mapping):
        raise MifalDevelopmentPatchError("E0-MR runtime authority is absent")
    _require_equal(
        {key: authority.get(key) for key in (
            "branch", "tracking_ref", "published_ref", "clean_committed_head_required",
            "upstream_baseline_bundle_commit", "upstream_baseline_bundle_parent",
            "physical_input_count",
        )},
        {
            "branch": "main",
            "tracking_ref": PUBLISHED_REF,
            "published_ref": "refs/heads/main",
            "clean_committed_head_required": True,
            "upstream_baseline_bundle_commit": PATCH_BASE_COMMIT,
            "upstream_baseline_bundle_parent": PATCH_BASE_PARENT,
            "physical_input_count": EXPECTED_RUNTIME_PHYSICAL_INPUT_COUNT,
        },
        "upstream authority",
    )
    _require_equal(set(authority), {
        "branch", "tracking_ref", "published_ref", "clean_committed_head_required",
        "upstream_baseline_bundle_commit", "upstream_baseline_bundle_parent",
        "physical_input_count", "physical_inputs",
    }, "authority keys")

    _require_equal(value.get("patch_scope"), {
        "exact_added_count": 9,
        "exact_modified_count": 0,
        "exact_deleted_count": 0,
        "paths": list(PATCH_PATHS),
    }, "H patch scope")
    _require_equal(value.get("roles"), {
        "training_target_end": "2018-12",
        "model_selection_origin_start": "2019-01",
        "model_selection_target_end": "2020-12",
        "calibration_threshold_start": "2021-01",
        "locked_evaluation_start": "2022-01",
        "origin_and_target_must_share_role": True,
        "holdout_locations_excluded": True,
        "outcome_values_opened_by_m0": False,
    }, "role policy")
    _require_equal(value.get("denominators"), {
        "common_origin_rows": 29196,
        "intent_origins": 9732,
        "development_locations": 353,
        "horizons_months": [1, 2, 3],
        "rows_by_horizon": {"1": 9732, "2": 9732, "3": 9732},
        "rows_by_time_role": {
            "training": 25056, "model_selection": 3183,
            "calibration_threshold": 957,
        },
        "origins_by_time_role": {
            "training": 8352, "model_selection": 1061,
            "calibration_threshold": 319,
        },
        "assignment_roles": ["development"],
        "origin_year_month_min": "1973-05",
        "origin_year_month_max": "2021-09",
        "target_year_month_min": "1973-06",
        "target_year_month_max": "2021-12",
        "evidence_group_snapshot_origins": {
            "eligible": 9732, "ineligible": 0, "with_4_groups": 9209,
            "with_3_groups": 505, "with_2_groups": 18,
            "with_1_group": 0, "with_0_groups": 0,
        },
        "evidence_group_snapshot_rows": {
            "eligible": 29196, "ineligible": 0, "with_4_groups": 27627,
            "with_3_groups": 1515, "with_2_groups": 54,
        },
    }, "denominators")

    strict_adapter = value.get("strict_adapter")
    if not isinstance(strict_adapter, Mapping):
        raise MifalDevelopmentPatchError("E0-MR strict adapter contract is absent")
    _require_equal(set(strict_adapter), {
        "implementation",
        "legacy_adapter_direct_import_authorized",
        "legacy_adapter_invocation_authorized",
        "legacy_adapter_data_projection_authorized",
        "package_initializer_symbol_loading",
        "exact_panel_projection_count",
        "exact_panel_projection",
        "variable_order",
        "variable_mapping",
        "evidence_groups",
        "minimum_observed_evidence_groups",
        "observed_variable_eligibility",
        "source_quality_formula",
        "source_quality_base",
        "missing_qc_ok_rate_fallback",
        "source_fit_policy",
        "age_days",
        "independence",
        "sigma_formula",
        "sigma_policy",
        "do_semantics",
        "no_temporal_carry",
        "forbidden_observed_lineage",
        "target_artifact_inputs",
        "target_columns_scanned",
    }, "strict adapter keys")
    _require_equal(strict_adapter.get("implementation"), "src/mifal/closure_panel_adapter.py", "adapter path")
    _require_equal(strict_adapter.get("legacy_adapter_direct_import_authorized"), False, "legacy direct-import ban")
    _require_equal(strict_adapter.get("legacy_adapter_invocation_authorized"), False, "legacy invocation ban")
    _require_equal(strict_adapter.get("legacy_adapter_data_projection_authorized"), False, "legacy projection ban")
    _require_equal(strict_adapter.get("package_initializer_symbol_loading"), "incidental_non_authoritative_no_io", "incidental package initialization")
    _require_equal(strict_adapter.get("exact_panel_projection_count"), 27, "projection count")
    _require_equal(strict_adapter.get("exact_panel_projection"), list(PANEL_PROJECTION), "panel projection")
    _require_equal(strict_adapter.get("variable_order"), list(VARIABLE_ORDER), "variable order")
    _require_equal(strict_adapter.get("evidence_groups"), EVIDENCE_GROUPS, "evidence groups")
    _require_equal(strict_adapter.get("minimum_observed_evidence_groups"), 2, "minimum evidence groups")
    _require_equal(strict_adapter.get("source_quality_formula"), "0_80_times_clip_qc_ok_rate_times_sqrt_min_n_obs_3_over_3", "source quality")
    _require_equal(strict_adapter.get("source_quality_base"), 0.80, "source quality base")
    _require_equal(strict_adapter.get("missing_qc_ok_rate_fallback"), 0.75, "missing QC fallback")
    _require_equal(strict_adapter.get("source_fit_policy"), "per_variable_locked_mapping", "source fit policy")
    _require_equal(strict_adapter.get("age_days"), 15.0, "observation age")
    _require_equal(strict_adapter.get("independence"), 1.0, "observation independence")
    _require_equal(strict_adapter.get("do_semantics"), "dissolved_oxygen_proxy_not_verified_bottom_oxygen", "DOb proxy")
    _require_equal(strict_adapter.get("no_temporal_carry"), True, "temporal carry ban")
    _require_equal(strict_adapter.get("observed_variable_eligibility"), "finite_value_and_n_obs_at_least_one", "observed-variable eligibility")
    _require_equal(strict_adapter.get("sigma_formula"), "observed_std_times_unit_scale_divided_by_sqrt_n_obs", "sigma formula")
    _require_equal(strict_adapter.get("sigma_policy"), "finite_nonnegative_formula_else_v5_default_sigma", "sigma fallback")
    _require_equal(strict_adapter.get("forbidden_observed_lineage"), [
        "observed_chlorophyll_current",
        "observed_chlorophyll_lagged",
        "observed_chlorophyll_derived",
        "observed_site_specific_memory",
        "risk_chlorophyll_proxy",
    ], "forbidden observed lineage")
    _require_equal(strict_adapter.get("target_artifact_inputs"), [], "target input ban")
    _require_equal(strict_adapter.get("target_columns_scanned"), [], "target scan ban")
    expected_mapping = {
        "Tw": {"value": "mean_temperature_C", "n_obs": "n_obs_temperature_C", "quality": "qc_ok_rate_temperature_C", "sigma": "std_temperature_C", "scale": 1.0, "source_fit": 1.0, "group": "temperature"},
        "TP": {"value": "mean_TP_ugL", "n_obs": "n_obs_TP_ugL", "quality": "qc_ok_rate_TP_ugL", "sigma": "std_TP_ugL", "scale": 1.0, "source_fit": 1.0, "group": "nutrients"},
        "TN": {"value": "mean_TN_ugL", "n_obs": "n_obs_TN_ugL", "quality": "qc_ok_rate_TN_ugL", "sigma": "std_TN_ugL", "scale": 0.001, "source_fit": 0.95, "group": "nutrients"},
        "Secchi": {"value": "mean_secchi_depth_m", "n_obs": "n_obs_secchi_depth_m", "quality": "qc_ok_rate_secchi_depth_m", "sigma": "std_secchi_depth_m", "scale": 1.0, "source_fit": 1.0, "group": "light"},
        "Turb": {"value": "mean_turbidity_NTU", "n_obs": "n_obs_turbidity_NTU", "quality": "qc_ok_rate_turbidity_NTU", "sigma": "std_turbidity_NTU", "scale": 1.0, "source_fit": 0.90, "group": "light"},
        "DOb": {"value": "mean_DO_mgL", "n_obs": "n_obs_DO_mgL", "quality": "qc_ok_rate_DO_mgL", "sigma": "std_DO_mgL", "scale": 1.0, "source_fit": 0.55, "group": "internal_do"},
    }
    _require_equal(strict_adapter.get("variable_mapping"), expected_mapping, "variable mapping")

    model = value.get("model")
    if not isinstance(model, Mapping):
        raise MifalDevelopmentPatchError("E0-MR model contract is absent")
    _require_equal(set(model), {
        "family", "core_path", "core_version", "configuration",
        "default_config_canonical_json_bytes", "default_config_sha256",
        "initial_state", "gammaM", "missing_memory_fallback_interval",
        "structural_memory_semantics", "observed_memory_inputs",
        "observed_chlorophyll_inputs", "parameter_tuning", "technical_seed",
        "logical_reuse_model_seeds", "stored_surface_count",
        "seed_replication_in_storage", "step_call", "raw_score_field",
        "candidate", "score_semantics", "predicted_bloom_probability_state",
        "calibration_applied", "ineligible_status", "ineligible_reason",
        "ineligible_row_policy",
    }, "model keys")
    expected_config_bytes, expected_config_sha = _default_config_digest()
    _require_equal(MIFAL_VERSION, "5.0.0", "physical MIFAL version")
    _require_equal(model.get("family"), "mifal_ed_t2_strict_no_chla_memory", "model family")
    _require_equal(model.get("core_path"), "src/mifal/ed_t2.py", "MIFAL core path")
    _require_equal(model.get("core_version"), "5.0.0", "MIFAL version")
    _require_equal(model.get("configuration"), "v5_dataclass_defaults_without_tuning", "MIFAL configuration")
    _require_equal(model.get("default_config_canonical_json_bytes"), expected_config_bytes, "default config bytes")
    _require_equal(model.get("default_config_sha256"), expected_config_sha, "default config digest")
    _require_equal(model.get("initial_state"), [0.05, 0.35], "initial structural state")
    _require_equal(model.get("gammaM"), 0.28, "memory weight")
    _require_equal(model.get("missing_memory_fallback_interval"), [0.0, 0.35], "memory fallback")
    _require_equal(model.get("structural_memory_semantics"), "global_constant_prior_not_observed_or_site_specific_memory", "structural memory semantics")
    _require_equal(model.get("observed_memory_inputs"), [], "observed memory ban")
    _require_equal(model.get("observed_chlorophyll_inputs"), [], "observed chlorophyll ban")
    _require_equal(model.get("parameter_tuning"), "forbidden", "tuning ban")
    _require_equal(model.get("technical_seed"), 1729, "technical seed")
    _require_equal(model.get("logical_reuse_model_seeds"), [1729, 20260612, 20260613, 20260614, 314159], "logical seed reuse")
    _require_equal(model.get("stored_surface_count"), 1, "stored surface count")
    _require_equal(model.get("seed_replication_in_storage"), "forbidden", "seed replication ban")
    _require_equal(model.get("step_call"), {
        "dt_days_formula": "horizon_months_times_30_4375",
        "days_per_horizon_month": 30.4375,
        "assimilate": False,
        "update_state": False,
        "compute_voi": False,
    }, "MIFAL call")
    _require_equal(model.get("candidate"), "mifal_ed_t2_v5_defaults", "candidate token")
    _require_equal(model.get("raw_score_field"), "risk_conservative", "raw score field")
    _require_equal(model.get("score_semantics"), "mifal_type2_conservative_raw_risk_uncalibrated", "score semantics")
    _require_equal(model.get("predicted_bloom_probability_state"), "null_until_future_common_calibration", "probability state")
    _require_equal(model.get("calibration_applied"), False, "calibration ban")
    _require_equal(model.get("ineligible_status"), "input_ineligible", "ineligible status")
    _require_equal(model.get("ineligible_reason"), "strict_non_chla_evidence_incomplete", "ineligible reason")
    _require_equal(model.get("ineligible_row_policy"), "retain_with_null_numeric_outputs", "ineligible row policy")

    outputs = value.get("outputs")
    if not isinstance(outputs, Mapping):
        raise MifalDevelopmentPatchError("E0-MR output contract is absent")
    _require_equal(outputs.get("exact_final_path_count"), 6, "final path count")
    _require_equal(outputs.get("exact_raw_prediction_rows"), 29196, "raw row count")
    _require_equal(outputs.get("raw_scores"), MIFAL_FINAL_PATHS[0], "raw output path")
    _require_equal(outputs.get("light_bundle"), {
        "model_spec": MIFAL_FINAL_PATHS[1],
        "lineage_audit": MIFAL_FINAL_PATHS[2],
        "availability": MIFAL_FINAL_PATHS[3],
        "report": MIFAL_FINAL_PATHS[4],
        "manifest": MIFAL_FINAL_PATHS[5],
    }, "light output paths")
    _require_equal(outputs.get("light_bundle_contract"), {
        "model_spec": "binds_core_v5_default_digest_call_flags_and_source_hashes",
        "lineage_audit": "binds_projection_groups_and_zero_forbidden_or_target_lineage",
        "availability": "exact_denominators_by_status_group_count_role_and_horizon",
        "report": "states_raw_uncalibrated_development_only_and_no_empirical_inference",
        "manifest": "binds_authority_inputs_sources_outputs_and_atomic_transaction",
    }, "light bundle contract")
    _require_equal(outputs.get("raw_prediction_contract"), expected_raw_prediction_contract(), "raw28 contract")
    _require_equal(outputs.get("manifest_written_last"), True, "manifest-last")
    _require_equal(outputs.get("forbidden_final_classes"), [
        "model_checkpoint",
        "fitted_preprocessor",
        "calibrator",
        "threshold",
        "target_derived_metric",
        "outcome_record",
    ], "forbidden output classes")
    publication = outputs.get("publication")
    _require_equal(publication, {
        "guard_path": MIFAL_OUTPUT_GUARD,
        "temporary_suffix": ".tmp",
        "parent_walk_no_follow": True,
        "no_clobber": True,
        "hardlink_publication": True,
        "rollback_owned_inode_only": True,
    }, "publication transaction")

    _require_equal(value.get("reproducibility"), {
        "execution_device": "cpu",
        "threadpool_limit": 1,
        "dependency_files": ["pyproject.toml", "poetry.lock"],
        "runtime_versions_recorded_in_manifest": True,
    }, "reproducibility")
    _require_equal(value.get("dvc"), {
        "authorized_during_h_or_p": False,
        "authorized_during_one_shot": False,
        "post_audit_registration_required": True,
        "raw_parquet_pointer": MIFAL_POINTER_PATH,
        "model_artifact_required": False,
        "models_dvc_must_remain_unchanged": True,
    }, "DVC policy")
    runtime_authorizations: dict[str, Any] = dict(UNPUBLISHED_AUTHORIZATIONS)
    runtime_authorizations.pop("effective_in_payload")
    runtime_authorizations.pop("publication_required")
    runtime_authorizations["outcome_access_log_required_state"] = "absent"
    _require_equal(value.get("authorizations"), runtime_authorizations, "runtime authorizations")

    if verify_physical_pins:
        _verify_runtime_physical_pins(value, repo_root=repo_root)
    return value


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def mifal_final_paths(runtime: Mapping[str, Any]) -> tuple[str, ...]:
    outputs = runtime.get("outputs")
    if not isinstance(outputs, Mapping):
        raise MifalDevelopmentPatchError("E0-MR output namespace is absent")
    light = outputs.get("light_bundle")
    if not isinstance(light, Mapping):
        raise MifalDevelopmentPatchError("E0-MR light output namespace is absent")
    observed = (
        str(outputs.get("raw_scores")),
        str(light.get("model_spec")),
        str(light.get("lineage_audit")),
        str(light.get("availability")),
        str(light.get("report")),
        str(light.get("manifest")),
    )
    if observed != MIFAL_FINAL_PATHS or len(set(observed)) != 6:
        raise MifalDevelopmentPatchError("E0-MR final namespace drifted")
    return observed


def mifal_output_namespace_absence(
    runtime: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = _root(repo_root)
    finals = mifal_final_paths(runtime)
    temporaries = tuple(f"{path}.tmp" for path in finals)
    pointer = str(runtime.get("dvc", {}).get("raw_parquet_pointer"))
    if pointer != MIFAL_POINTER_PATH:
        raise MifalDevelopmentPatchError("E0-MR future pointer path drifted")
    pointer_temporary = f"{pointer}.tmp"
    guard = str(runtime.get("outputs", {}).get("publication", {}).get("guard_path"))
    if guard != MIFAL_OUTPUT_GUARD:
        raise MifalDevelopmentPatchError("E0-MR one-shot guard path drifted")
    present_finals = [path for path in finals if _lexists(root / path)]
    present_temporaries = [path for path in temporaries if _lexists(root / path)]
    pointer_present = _lexists(root / pointer)
    pointer_temporary_present = _lexists(root / pointer_temporary)
    guard_present = _lexists(root / guard)
    if (
        present_finals
        or present_temporaries
        or pointer_present
        or pointer_temporary_present
        or guard_present
    ):
        raise MifalDevelopmentPatchError(
            "E0-MR output namespace is not empty: "
            f"finals={present_finals}, temporaries={present_temporaries}, "
            f"pointer={pointer_present}, pointer_tmp={pointer_temporary_present}, "
            f"guard={guard_present}"
        )
    return {
        "final_count": 6,
        "final_paths": list(finals),
        "final_paths_sha256": _path_digest(finals),
        "all_final_absent": True,
        "temporary_count": 6,
        "temporary_paths": list(temporaries),
        "temporary_paths_sha256": _path_digest(temporaries),
        "all_temporary_absent": True,
        "future_pointer_path": pointer,
        "future_pointer_absent": True,
        "future_pointer_temporary_path": pointer_temporary,
        "future_pointer_temporary_absent": True,
        "guard_path": guard,
        "guard_absent": True,
    }


def _git(*args: str, repo_root: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=_root(repo_root),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise MifalDevelopmentPatchError(
            f"git {' '.join(args)} failed: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def _live_remote_main_head(*, repo_root: Path | None = None) -> str:
    output = _git(
        "ls-remote",
        "--exit-code",
        "origin",
        "refs/heads/main",
        repo_root=repo_root,
    )
    lines = [line for line in output.splitlines() if line]
    if len(lines) != 1:
        raise MifalDevelopmentPatchError("Remote main observation is not unique")
    fields = lines[0].split("\t")
    if (
        len(fields) != 2
        or fields[1] != "refs/heads/main"
        or len(fields[0]) != 40
        or any(character not in "0123456789abcdef" for character in fields[0])
    ):
        raise MifalDevelopmentPatchError("Remote main observation is malformed")
    return fields[0]


def _single_parent(commit: str, *, repo_root: Path | None = None) -> str:
    fields = _git(
        "rev-list", "--parents", "-n", "1", commit, repo_root=repo_root
    ).split()
    if len(fields) != 2 or fields[0] != commit:
        raise MifalDevelopmentPatchError(
            f"Commit is not a direct non-merge child: {commit}"
        )
    return fields[1]


def _observed_diff_entries(
    base: str,
    head: str,
    *,
    repo_root: Path | None = None,
) -> list[dict[str, str]]:
    output = _git(
        "diff-tree",
        "--no-commit-id",
        "--name-status",
        "-r",
        base,
        head,
        repo_root=repo_root,
    )
    entries: list[dict[str, str]] = []
    for line in output.splitlines():
        if not line:
            continue
        fields = line.split("\t")
        if len(fields) != 2 or fields[0] not in {"A", "M", "D"}:
            raise MifalDevelopmentPatchError(f"Unsupported Git diff entry: {line}")
        entries.append({"status": fields[0], "path": fields[1]})
    return entries


def _validate_h_component_records(
    h_patch: Mapping[str, Any],
) -> list[dict[str, Any]]:
    paths = h_patch.get("paths")
    components = h_patch.get("components")
    if (
        h_patch.get("base_commit") != PATCH_BASE_COMMIT
        or h_patch.get("added_count") != 9
        or h_patch.get("modified_count") != 0
        or h_patch.get("deleted_count") != 0
        or paths != list(PATCH_PATHS)
        or not isinstance(components, list)
        or len(components) != 9
    ):
        raise MifalDevelopmentPatchError("E0-MR H scope drifted")
    normalized: list[dict[str, Any]] = []
    for index, path in enumerate(PATCH_PATHS):
        candidate = components[index]
        if not isinstance(candidate, Mapping):
            raise MifalDevelopmentPatchError("E0-MR H component is not a mapping")
        record = dict(candidate)
        if (
            set(record) != {"path", "role", "bytes", "sha256"}
            or record.get("path") != path
            or record.get("role") != PATCH_COMPONENT_ROLES[path]
            or not isinstance(record.get("bytes"), int)
            or int(record["bytes"]) < 1
            or not isinstance(record.get("sha256"), str)
            or len(str(record["sha256"])) != 64
            or any(
                character not in "0123456789abcdef"
                for character in str(record["sha256"])
            )
        ):
            raise MifalDevelopmentPatchError(
                f"E0-MR H component binding drifted: {path}"
            )
        normalized.append(record)
    if len({str(record["path"]) for record in normalized}) != 9:
        raise MifalDevelopmentPatchError("E0-MR H components contain duplicates")
    if h_patch.get("paths_sha256") != _path_digest(PATCH_PATHS):
        raise MifalDevelopmentPatchError("E0-MR H path digest drifted")
    if h_patch.get("components_sha256") != _record_digest(normalized):
        raise MifalDevelopmentPatchError("E0-MR H component digest drifted")
    return normalized


def _git_blob_record(
    commit: str,
    path: str,
    *,
    role: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=_root(repo_root),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise MifalDevelopmentPatchError(f"E0-MR cannot reconstruct H blob: {path}")
    return {
        "path": path,
        "role": role,
        "bytes": len(result.stdout),
        "sha256": _sha256_bytes(result.stdout),
    }


def _require_git_mode_100644(
    commit: str,
    path: str,
    *,
    repo_root: Path | None = None,
) -> None:
    output = _git("ls-tree", commit, "--", path, repo_root=repo_root)
    fields = output.split(maxsplit=3)
    if len(fields) != 4 or fields[0] != "100644" or fields[1] != "blob":
        raise MifalDevelopmentPatchError(
            f"E0-MR Git mode is not exact 100644: {path}"
        )


def _reconstruct_h_components(
    payload: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> list[dict[str, Any]]:
    repository = payload.get("repository")
    h_patch = payload.get("h_patch")
    if not isinstance(repository, Mapping) or not isinstance(h_patch, Mapping):
        raise MifalDevelopmentPatchError("E0-MR H authority is absent")
    h_head = repository.get("head")
    if not isinstance(h_head, str) or len(h_head) != 40:
        raise MifalDevelopmentPatchError("E0-MR H commit is malformed")
    if _single_parent(h_head, repo_root=repo_root) != PATCH_BASE_COMMIT:
        raise MifalDevelopmentPatchError("E0-MR H parent drifted")
    entries = _observed_diff_entries(PATCH_BASE_COMMIT, h_head, repo_root=repo_root)
    expected = [{"status": "A", "path": path} for path in PATCH_PATHS]
    if sorted(entries, key=lambda item: item["path"]) != expected:
        raise MifalDevelopmentPatchError("H-E0-MR is not exactly nine additions")
    locked = _validate_h_component_records(h_patch)
    reconstructed = [
        _git_blob_record(
            h_head,
            path,
            role=PATCH_COMPONENT_ROLES[path],
            repo_root=repo_root,
        )
        for path in PATCH_PATHS
    ]
    for path in PATCH_PATHS:
        _require_git_mode_100644(h_head, path, repo_root=repo_root)
    if reconstructed != locked:
        raise MifalDevelopmentPatchError("E0-MR H Git blobs differ from the lock")
    current = [
        _file_record(
            Path(path),
            role=PATCH_COMPONENT_ROLES[path],
            repo_root=repo_root,
        )
        for path in PATCH_PATHS
    ]
    if current != locked:
        raise MifalDevelopmentPatchError("E0-MR H files drifted after publication")
    return reconstructed


def _require_prelock_control_namespace_absent(
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = _root(repo_root)
    lock_temp = Path(f"{DEFAULT_PATCH_LOCK_PATH.as_posix()}.tmp")
    manifest_temp = Path(f"{DEFAULT_PATCH_MANIFEST_PATH.as_posix()}.tmp")
    observed = {
        "p_lock_path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "p_lock_absent": not _lexists(root / DEFAULT_PATCH_LOCK_PATH),
        "p_manifest_path": DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
        "p_manifest_absent": not _lexists(root / DEFAULT_PATCH_MANIFEST_PATH),
        "p_temporaries_absent": not _lexists(root / lock_temp)
        and not _lexists(root / manifest_temp),
        "locker_guard_path": LOCKER_GUARD_PATH.as_posix(),
        "locker_guard_absent": not _lexists(root / LOCKER_GUARD_PATH),
    }
    if not all(
        observed[key]
        for key in (
            "p_lock_absent",
            "p_manifest_absent",
            "p_temporaries_absent",
            "locker_guard_absent",
        )
    ):
        raise MifalDevelopmentPatchError("E0-MR P control namespace is not empty")
    return observed


def _runtime_contract_binding(
    *,
    runtime_record: Mapping[str, Any],
    physical_inputs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    normalized_inputs = [dict(record) for record in physical_inputs]
    return {
        "record": dict(runtime_record),
        "schema_subset_verified": True,
        "pins_verified": True,
        "physical_input_count": EXPECTED_RUNTIME_PHYSICAL_INPUT_COUNT,
        "physical_inputs": normalized_inputs,
        "physical_inputs_sha256": _record_digest(normalized_inputs),
        "panel_projection_count": len(PANEL_PROJECTION),
        "panel_projection": list(PANEL_PROJECTION),
        "evidence_groups": EVIDENCE_GROUPS,
        "minimum_observed_evidence_groups": 2,
        "default_config_sha256": _default_config_digest()[1],
        "raw_prediction_contract": expected_raw_prediction_contract(),
        "exact_raw_prediction_rows": 29196,
        "exact_final_path_count": 6,
        "target_artifact_inputs": [],
        "target_columns_scanned": [],
    }


def _derived_prelock_binding(
    runtime: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = _root(repo_root)
    namespace = mifal_output_namespace_absence(runtime, repo_root=root)
    e0_m_present = [path for path in E0_M_PATHS if _lexists(root / path)]
    outcome_present = _lexists(root / OUTCOME_ACCESS_LOG)
    p_temporaries = (
        Path(f"{DEFAULT_PATCH_LOCK_PATH.as_posix()}.tmp"),
        Path(f"{DEFAULT_PATCH_MANIFEST_PATH.as_posix()}.tmp"),
    )
    if e0_m_present or outcome_present:
        raise MifalDevelopmentPatchError("E0-M or outcome-access log exists before E0-MR")
    if any(_lexists(root / path) for path in p_temporaries):
        raise MifalDevelopmentPatchError("E0-MR P temporary output exists")
    if _lexists(root / LOCKER_GUARD_PATH):
        raise MifalDevelopmentPatchError("E0-MR locker guard remains active")
    return {
        "output_namespace": namespace,
        "e0_m_paths": list(E0_M_PATHS),
        "all_e0_m_paths_absent": True,
        "outcome_access_log_path": OUTCOME_ACCESS_LOG,
        "outcome_access_log_absent": True,
        "p_lock_path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "p_lock_absent": True,
        "p_manifest_path": DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
        "p_manifest_absent": True,
        "p_temporaries_absent": True,
        "locker_guard_path": LOCKER_GUARD_PATH.as_posix(),
        "locker_guard_absent": True,
        "target_paths_opened": [],
        "dvc_commands_run": False,
        "scientific_network_commands_run": False,
        "git_remote_verification_run": True,
        "data_execution_run": False,
        "auditor_run": False,
        "future_outcomes_accessed": False,
    }


def collect_mifal_development_patch_prelock_state(
    *,
    repo_root: Path | None = None,
    verify_remote: bool = True,
) -> dict[str, Any]:
    """Collect exact H state without M0, DVC, target, or outcome execution."""
    if verify_remote is not True:
        raise MifalDevelopmentPatchError("E0-MR requires live remote verification")
    root = _root(repo_root)
    head = _git("rev-parse", "HEAD", repo_root=root)
    parent = _single_parent(head, repo_root=root)
    branch = _git("branch", "--show-current", repo_root=root)
    tracking = _git("rev-parse", PUBLISHED_REF, repo_root=root)
    remote = _live_remote_main_head(repo_root=root)
    if (
        parent != PATCH_BASE_COMMIT
        or branch != "main"
        or tracking != head
        or remote != head
    ):
        raise MifalDevelopmentPatchError("Published H topology/ref alignment drifted")
    if _git("status", "--porcelain=v1", "--untracked-files=all", repo_root=root):
        raise MifalDevelopmentPatchError("E0-MR H repository must be clean")
    entries = _observed_diff_entries(PATCH_BASE_COMMIT, head, repo_root=root)
    expected_entries = [{"status": "A", "path": path} for path in PATCH_PATHS]
    if sorted(entries, key=lambda item: item["path"]) != expected_entries:
        raise MifalDevelopmentPatchError("H-E0-MR is not exactly nine additions")

    components = [
        _file_record(
            Path(path),
            role=PATCH_COMPONENT_ROLES[path],
            repo_root=root,
        )
        for path in PATCH_PATHS
    ]
    runtime = load_and_validate_mifal_development_runtime(
        repo_root=root,
        verify_physical_pins=False,
    )
    physical_inputs = _verify_runtime_physical_pins(runtime, repo_root=root)
    namespace = mifal_output_namespace_absence(runtime, repo_root=root)
    control_namespace = _require_prelock_control_namespace_absent(repo_root=root)
    e0_m_present = [path for path in E0_M_PATHS if _lexists(root / path)]
    outcome_present = _lexists(root / OUTCOME_ACCESS_LOG)
    if e0_m_present or outcome_present:
        raise MifalDevelopmentPatchError("E0-M or outcome-access log exists before E0-MR")
    runtime_record = next(
        record
        for record in components
        if record["path"] == DEFAULT_RUNTIME_PATH.as_posix()
    )
    return {
        "repository": {
            "head": head,
            "parent": parent,
            "branch": branch,
            "tracking_ref": PUBLISHED_REF,
            "tracking_head": tracking,
            "remote_head": remote,
            "remote_observation_mode": "live_remote_main_verified",
            "worktree_status": "clean",
        },
        "h_patch": {
            "base_commit": PATCH_BASE_COMMIT,
            "added_count": 9,
            "modified_count": 0,
            "deleted_count": 0,
            "paths": list(PATCH_PATHS),
            "paths_sha256": _path_digest(PATCH_PATHS),
            "components": components,
            "components_sha256": _record_digest(components),
        },
        "runtime_contract": _runtime_contract_binding(
            runtime_record=runtime_record,
            physical_inputs=physical_inputs,
        ),
        "prelock": {
            "output_namespace": namespace,
            "e0_m_paths": list(E0_M_PATHS),
            "all_e0_m_paths_absent": True,
            "outcome_access_log_path": OUTCOME_ACCESS_LOG,
            "outcome_access_log_absent": True,
            **control_namespace,
            "target_paths_opened": [],
            "dvc_commands_run": False,
            "scientific_network_commands_run": False,
            "git_remote_verification_run": True,
            "data_execution_run": False,
            "auditor_run": False,
            "future_outcomes_accessed": False,
        },
    }


def build_mifal_development_patch_lock_payload(
    prelock: Mapping[str, Any],
    verification: Mapping[str, Any],
    *,
    created_at_utc: str,
) -> dict[str, Any]:
    """Build the unpublished payload; no execution flag becomes effective here."""
    return {
        "lock_version": LOCK_VERSION,
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "experiment_id": EXPERIMENT_ID,
        "surface_id": SURFACE_ID,
        "model_id": MODEL_ID,
        "status": "locked_unpublished",
        "created_at_utc": created_at_utc,
        "repository": dict(prelock["repository"]),
        "h_patch": dict(prelock["h_patch"]),
        "runtime_contract": dict(prelock["runtime_contract"]),
        "prelock": dict(prelock["prelock"]),
        "verification": dict(verification),
        "authorizations": dict(UNPUBLISHED_AUTHORIZATIONS),
        "seals": dict(PATCH_SEALS),
    }


def _validate_timestamp(value: Any) -> None:
    if not isinstance(value, str):
        raise MifalDevelopmentPatchError("Lock timestamp must be a string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MifalDevelopmentPatchError("Lock timestamp is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MifalDevelopmentPatchError("Lock timestamp must include timezone")


def _validate_command_evidence(
    value: Any,
    *,
    expected_command: Sequence[str],
    context: str,
    exact_stdout: str | None = None,
) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "command",
        "returncode",
        "stdout_sha256",
        "stderr_sha256",
        "stdout_line_count",
        "stderr_line_count",
    }:
        raise MifalDevelopmentPatchError(f"E0-MR {context} evidence dialect drifted")
    if value.get("command") != list(expected_command) or value.get("returncode") != 0:
        raise MifalDevelopmentPatchError(f"E0-MR {context} command/result drifted")
    for key in ("stdout_sha256", "stderr_sha256"):
        digest = value.get(key)
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise MifalDevelopmentPatchError(f"E0-MR {context} digest drifted")
    for key in ("stdout_line_count", "stderr_line_count"):
        if not isinstance(value.get(key), int) or int(value[key]) < 0:
            raise MifalDevelopmentPatchError(f"E0-MR {context} line count drifted")
    empty_sha = _sha256_bytes(b"")
    if value.get("stderr_sha256") != empty_sha or value.get("stderr_line_count") != 0:
        raise MifalDevelopmentPatchError(f"E0-MR {context} stderr evidence drifted")
    if exact_stdout is not None and (
        value.get("stdout_sha256") != _sha256_bytes(exact_stdout.encode("utf-8"))
        or value.get("stdout_line_count") != len(exact_stdout.splitlines())
    ):
        raise MifalDevelopmentPatchError(f"E0-MR {context} stdout evidence drifted")


def _validate_verification_binding(
    value: Any,
    *,
    repo_root: Path | None = None,
) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "schema_preflight",
        "full_type_check",
        "focused_tests",
        "poetry_check",
        "publication_guard",
        "git_diff_check",
    }:
        raise MifalDevelopmentPatchError("E0-MR verification bundle drifted")
    expected_preflight = preflight_mifal_development_patch_schema(repo_root=repo_root)
    if value.get("schema_preflight") != expected_preflight:
        raise MifalDevelopmentPatchError("E0-MR schema preflight evidence drifted")
    _validate_command_evidence(
        value.get("full_type_check"),
        expected_command=TYPE_CHECK_COMMAND,
        context="full type check",
        exact_stdout="All checks passed!\n",
    )
    _validate_command_evidence(
        value.get("poetry_check"),
        expected_command=POETRY_CHECK_COMMAND,
        context="poetry check",
        exact_stdout="All set!\n",
    )
    _validate_command_evidence(
        value.get("publication_guard"),
        expected_command=PUBLICATION_GUARD_COMMAND,
        context="publication guard",
        exact_stdout=(
            "Checking tracked files before publication...\n"
            "OK: tracked files look publication-ready.\n"
        ),
    )
    _validate_command_evidence(
        value.get("git_diff_check"),
        expected_command=DIFF_CHECK_COMMAND,
        context="git diff check",
        exact_stdout="",
    )
    focused = value.get("focused_tests")
    if not isinstance(focused, Mapping):
        raise MifalDevelopmentPatchError("E0-MR focused evidence is absent")
    common_evidence = {
        key: focused.get(key)
        for key in (
            "command",
            "returncode",
            "stdout_sha256",
            "stderr_sha256",
            "stdout_line_count",
            "stderr_line_count",
        )
    }
    _validate_command_evidence(
        common_evidence,
        expected_command=FOCUSED_TEST_COMMAND,
        context="focused tests",
    )
    if set(focused) != {
        *common_evidence,
        "test_count",
        "skipped_count",
        "deselected_count",
    }:
        raise MifalDevelopmentPatchError("E0-MR focused summary dialect drifted")
    if FOCUSED_TEST_COUNT < 1:
        raise MifalDevelopmentPatchError("E0-MR focused count has not been frozen")
    if (
        focused.get("test_count") != FOCUSED_TEST_COUNT
        or focused.get("skipped_count") != 0
        or focused.get("deselected_count") != 0
    ):
        raise MifalDevelopmentPatchError("E0-MR focused summary drifted")


def _validate_repository_binding(
    value: Any,
    *,
    repo_root: Path | None = None,
) -> str:
    if not isinstance(value, Mapping) or set(value) != {
        "head",
        "parent",
        "branch",
        "tracking_ref",
        "tracking_head",
        "remote_head",
        "remote_observation_mode",
        "worktree_status",
    }:
        raise MifalDevelopmentPatchError("E0-MR repository dialect drifted")
    h_head = value.get("head")
    if (
        not isinstance(h_head, str)
        or len(h_head) != 40
        or any(character not in "0123456789abcdef" for character in h_head)
        or value.get("parent") != PATCH_BASE_COMMIT
        or value.get("branch") != "main"
        or value.get("tracking_ref") != PUBLISHED_REF
        or value.get("tracking_head") != h_head
        or value.get("remote_head") != h_head
        or value.get("remote_observation_mode") != "live_remote_main_verified"
        or value.get("worktree_status") != "clean"
    ):
        raise MifalDevelopmentPatchError("E0-MR repository binding drifted")
    if _single_parent(h_head, repo_root=repo_root) != PATCH_BASE_COMMIT:
        raise MifalDevelopmentPatchError("E0-MR locked H parent drifted")
    root = _root(repo_root)
    current_head = _git("rev-parse", "HEAD", repo_root=root)
    current_branch = _git("branch", "--show-current", repo_root=root)
    current_tracking = _git("rev-parse", PUBLISHED_REF, repo_root=root)
    current_remote = _live_remote_main_head(repo_root=root)
    if current_branch != "main":
        raise MifalDevelopmentPatchError("E0-MR current branch drifted")
    status = _git("status", "--porcelain=v1", "--untracked-files=all", repo_root=root)
    if current_head == h_head:
        if current_tracking != h_head or current_remote != h_head:
            raise MifalDevelopmentPatchError("E0-MR current H refs drifted")
        allowed = {
            DEFAULT_PATCH_LOCK_PATH.as_posix(),
            DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
        }
        status_paths = {
            line[3:]
            for line in status.splitlines()
            if len(line) >= 4
        }
        if status_paths.difference(allowed):
            raise MifalDevelopmentPatchError("E0-MR H worktree contains unrelated changes")
    else:
        if _single_parent(current_head, repo_root=root) != h_head:
            raise MifalDevelopmentPatchError("E0-MR current commit is outside H/P topology")
        if current_tracking != current_head or current_remote != current_head or status:
            raise MifalDevelopmentPatchError("E0-MR published P refs/worktree drifted")
    return h_head


def validate_mifal_development_patch_lock_payload(
    payload: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    schema = _load_regular_json(
        DEFAULT_PATCH_LOCK_SCHEMA,
        context="E0-MR lock schema",
        repo_root=repo_root,
    )
    try:
        validate_json_schema(payload, schema)
    except ClosureContractError as exc:
        raise MifalDevelopmentPatchError(str(exc)) from exc
    _validate_timestamp(payload.get("created_at_utc"))
    if payload.get("authorizations") != UNPUBLISHED_AUTHORIZATIONS:
        raise MifalDevelopmentPatchError("Unpublished E0-MR authorizations drifted")
    if payload.get("seals") != PATCH_SEALS:
        raise MifalDevelopmentPatchError("E0-MR seals drifted")
    repository = payload.get("repository")
    h_head = _validate_repository_binding(repository, repo_root=repo_root)
    h_patch = payload.get("h_patch")
    if not isinstance(h_patch, Mapping):
        raise MifalDevelopmentPatchError("E0-MR H payload is absent")
    h_components = _validate_h_component_records(h_patch)
    reconstructed = _reconstruct_h_components(payload, repo_root=repo_root)
    if reconstructed != h_components:
        raise MifalDevelopmentPatchError("E0-MR H reconstruction drifted")
    runtime_contract = payload.get("runtime_contract")
    if not isinstance(runtime_contract, Mapping):
        raise MifalDevelopmentPatchError("E0-MR runtime lock binding is absent")
    runtime = load_and_validate_mifal_development_runtime(
        repo_root=repo_root,
        verify_physical_pins=False,
    )
    physical_inputs = _verify_runtime_physical_pins(runtime, repo_root=repo_root)
    runtime_record = next(
        record
        for record in h_components
        if record["path"] == DEFAULT_RUNTIME_PATH.as_posix()
    )
    expected_runtime_contract = _runtime_contract_binding(
        runtime_record=runtime_record,
        physical_inputs=physical_inputs,
    )
    if dict(runtime_contract) != expected_runtime_contract:
        raise MifalDevelopmentPatchError("E0-MR complete runtime binding drifted")
    expected_prelock = _derived_prelock_binding(runtime, repo_root=repo_root)
    if payload.get("prelock") != expected_prelock:
        raise MifalDevelopmentPatchError("E0-MR complete prelock binding drifted")
    if h_head != payload["repository"]["tracking_head"]:
        raise MifalDevelopmentPatchError("E0-MR repository/H binding drifted")
    _validate_verification_binding(payload.get("verification"), repo_root=repo_root)
    return dict(payload)


def _expected_companion(
    payload: Mapping[str, Any],
    lock_record: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    del repo_root  # Signature is explicit; construction uses only locked records.
    h_patch = payload.get("h_patch")
    runtime_contract = payload.get("runtime_contract")
    if not isinstance(h_patch, Mapping) or not isinstance(runtime_contract, Mapping):
        raise MifalDevelopmentPatchError("Cannot construct E0-MR companion inputs")
    h_components = _validate_h_component_records(h_patch)
    physical_inputs = runtime_contract.get("physical_inputs")
    if not isinstance(physical_inputs, list):
        raise MifalDevelopmentPatchError("Cannot construct E0-MR physical inputs")
    inputs = [dict(record) for record in (*h_components, *physical_inputs)]
    inputs.sort(key=lambda record: str(record.get("path")))
    paths = [str(record.get("path")) for record in inputs]
    if len(inputs) != EXPECTED_COMPANION_INPUT_COUNT or len(set(paths)) != len(inputs):
        raise MifalDevelopmentPatchError(
            "E0-MR companion must bind exactly 32 unique physical inputs"
        )
    locker_record = next(
        dict(record)
        for record in h_components
        if record["path"]
        == "src/experiments/lock_closure_mifal_development_patch.py"
    )
    normalized_lock = dict(lock_record)
    if (
        set(normalized_lock) != {"path", "role", "bytes", "sha256"}
        or normalized_lock.get("path") != DEFAULT_PATCH_LOCK_PATH.as_posix()
        or normalized_lock.get("role") != "mifal_development_patch_lock"
    ):
        raise MifalDevelopmentPatchError("E0-MR lock output record drifted")
    return {
        "manifest_version": "closure_mifal_development_patch_lock_manifest_v1",
        "gate": PATCH_GATE,
        "status": "completed",
        "script": locker_record,
        "inputs": inputs,
        "historical_inputs": [],
        "historical_inputs_compared_to_current_paths": False,
        "outputs": [normalized_lock],
        "physical_inputs_only": True,
        "manifest_written_last": True,
        "dvc_commands_run": False,
        "network_commands_run": True,
        "data_execution_run": False,
        "future_outcomes_accessed": False,
    }


def _validate_companion(
    payload: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    lock_record = _file_record(
        DEFAULT_PATCH_LOCK_PATH,
        role="mifal_development_patch_lock",
        repo_root=repo_root,
    )
    companion = _load_regular_json(
        DEFAULT_PATCH_MANIFEST_PATH,
        context="E0-MR companion",
        repo_root=repo_root,
    )
    if _read_regular_bytes(DEFAULT_PATCH_MANIFEST_PATH, repo_root=repo_root) != _canonical_json(companion):
        raise MifalDevelopmentPatchError("E0-MR companion is not canonical JSON")
    expected = _expected_companion(payload, lock_record, repo_root=repo_root)
    if companion != expected:
        raise MifalDevelopmentPatchError("E0-MR companion drifted")
    companion_record = _file_record(
        DEFAULT_PATCH_MANIFEST_PATH,
        role="mifal_development_patch_lock_manifest",
        repo_root=repo_root,
    )
    return lock_record, companion, companion_record


def _validate_p_publication(
    payload: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
    verify_remote: bool = True,
) -> dict[str, str]:
    if verify_remote is not True:
        raise MifalDevelopmentPatchError("E0-MR P requires live remote verification")
    root = _root(repo_root)
    repository = payload.get("repository")
    if not isinstance(repository, Mapping):
        raise MifalDevelopmentPatchError("E0-MR repository binding is absent")
    h_head = str(repository.get("head"))
    head = _git("rev-parse", "HEAD", repo_root=root)
    parent = _single_parent(head, repo_root=root)
    tracking = _git("rev-parse", PUBLISHED_REF, repo_root=root)
    remote = _live_remote_main_head(repo_root=root)
    if parent != h_head or tracking != head or remote != head:
        raise MifalDevelopmentPatchError("Published P topology/ref alignment drifted")
    if _git("branch", "--show-current", repo_root=root) != "main":
        raise MifalDevelopmentPatchError("Published P branch drifted")
    if _git("status", "--porcelain=v1", "--untracked-files=all", repo_root=root):
        raise MifalDevelopmentPatchError("Published P repository must be clean")
    entries = _observed_diff_entries(parent, head, repo_root=root)
    expected = [
        {"status": "A", "path": DEFAULT_PATCH_LOCK_PATH.as_posix()},
        {"status": "A", "path": DEFAULT_PATCH_MANIFEST_PATH.as_posix()},
    ]
    if sorted(entries, key=lambda item: item["path"]) != expected:
        raise MifalDevelopmentPatchError("P-E0-MR is not exactly lock+companion")
    for path in (DEFAULT_PATCH_LOCK_PATH, DEFAULT_PATCH_MANIFEST_PATH):
        _require_git_mode_100644(head, path.as_posix(), repo_root=root)
    _reconstruct_h_components(payload, repo_root=root)
    runtime = load_and_validate_mifal_development_runtime(
        repo_root=root,
        verify_physical_pins=False,
    )
    observed_inputs = _verify_runtime_physical_pins(runtime, repo_root=root)
    runtime_contract = payload.get("runtime_contract")
    if (
        not isinstance(runtime_contract, Mapping)
        or runtime_contract.get("physical_inputs") != observed_inputs
        or runtime_contract.get("physical_inputs_sha256")
        != _record_digest(observed_inputs)
    ):
        raise MifalDevelopmentPatchError("Published E0-MR physical inputs drifted")
    mifal_output_namespace_absence(runtime, repo_root=root)
    if any(_lexists(root / path) for path in E0_M_PATHS):
        raise MifalDevelopmentPatchError("E0-M exists before M0 one-shot")
    if _lexists(root / OUTCOME_ACCESS_LOG):
        raise MifalDevelopmentPatchError("Outcome access log exists before M0 one-shot")
    return {"h_patch_head": parent, "p_patch_head": head, "remote_head": remote}


def load_and_validate_mifal_development_patch_lock(
    lock_path: Path = DEFAULT_PATCH_LOCK_PATH,
    *,
    repo_root: Path | None = None,
    require_published: bool = False,
    verify_remote: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if lock_path != DEFAULT_PATCH_LOCK_PATH:
        raise MifalDevelopmentPatchError("E0-MR requires the closed default lock path")
    if verify_remote is not True:
        raise MifalDevelopmentPatchError("E0-MR requires live remote verification")
    preflight_mifal_development_patch_schema(repo_root=repo_root)
    payload = _load_regular_json(lock_path, context="E0-MR lock", repo_root=repo_root)
    if _read_regular_bytes(lock_path, repo_root=repo_root) != _canonical_json(payload):
        raise MifalDevelopmentPatchError("E0-MR lock is not canonical JSON")
    validated = validate_mifal_development_patch_lock_payload(
        payload,
        repo_root=repo_root,
    )
    lock_record, _companion, companion_record = _validate_companion(
        validated,
        repo_root=repo_root,
    )
    repository = validated.get("repository")
    if not isinstance(repository, Mapping):
        raise MifalDevelopmentPatchError("E0-MR repository binding is absent")
    if require_published:
        publication = _validate_p_publication(
            validated,
            repo_root=repo_root,
            verify_remote=verify_remote,
        )
    else:
        root = _root(repo_root)
        head = _git("rev-parse", "HEAD", repo_root=root)
        tracking = _git("rev-parse", PUBLISHED_REF, repo_root=root)
        remote = _live_remote_main_head(repo_root=root)
        if head != repository.get("head") or tracking != head or remote != head:
            raise MifalDevelopmentPatchError("Unpublished E0-MR H refs drifted")
        _reconstruct_h_components(validated, repo_root=root)
        runtime = load_and_validate_mifal_development_runtime(
            repo_root=root,
            verify_physical_pins=False,
        )
        observed_inputs = _verify_runtime_physical_pins(runtime, repo_root=root)
        runtime_contract = validated.get("runtime_contract")
        if (
            not isinstance(runtime_contract, Mapping)
            or runtime_contract.get("physical_inputs") != observed_inputs
        ):
            raise MifalDevelopmentPatchError("Unpublished E0-MR inputs drifted")
        mifal_output_namespace_absence(runtime, repo_root=root)
        publication = {
            "h_patch_head": head,
            "p_patch_head": "",
            "remote_head": remote,
        }
    summary = {
        **publication,
        "lock_sha256": lock_record["sha256"],
        "companion_sha256": companion_record["sha256"],
    }
    return validated, summary


def load_effective_mifal_development_authority(
    *,
    repo_root: Path | None = None,
    verify_remote: bool = True,
) -> dict[str, Any]:
    """Return the only effective M0 flags after exact P publication."""
    payload, publication = load_and_validate_mifal_development_patch_lock(
        repo_root=repo_root,
        require_published=True,
        verify_remote=verify_remote,
    )
    h_patch = payload["h_patch"]
    runtime_contract = payload["runtime_contract"]
    components = h_patch["components"]
    physical_inputs = runtime_contract["physical_inputs"]

    def component_sha(path: str) -> str:
        return next(record["sha256"] for record in components if record["path"] == path)

    def input_sha(path: str) -> str:
        return next(record["sha256"] for record in physical_inputs if record["path"] == path)

    return {
        "gate": PATCH_GATE,
        "status": "effective_preflight_passed",
        **EFFECTIVE_AUTHORIZATIONS,
        "h_patch_head": publication["h_patch_head"],
        "p_patch_head": publication["p_patch_head"],
        "lock_sha256": publication["lock_sha256"],
        "companion_sha256": publication["companion_sha256"],
        "runtime_sha256": runtime_contract["record"]["sha256"],
        "h_components_sha256": h_patch["components_sha256"],
        "physical_inputs_sha256": runtime_contract["physical_inputs_sha256"],
        "runner_sha256": component_sha("src/experiments/run_closure_mifal.py"),
        "adapter_sha256": component_sha("src/mifal/closure_panel_adapter.py"),
        "mifal_core_sha256": input_sha("src/mifal/ed_t2.py"),
        "raw_prediction_contract": expected_raw_prediction_contract(),
        "exact_raw_prediction_rows": 29196,
        "minimum_observed_evidence_groups": 2,
    }


def require_mifal_development_authority(
    *,
    repo_root: Path | None = None,
    verify_remote: bool = True,
) -> dict[str, Any]:
    """Runner gate; must be the first operation after CLI argument parsing."""
    if verify_remote is not True:
        raise MifalDevelopmentPatchError("E0-MR requires tracking-ref verification")
    return load_effective_mifal_development_authority(
        repo_root=repo_root,
        verify_remote=verify_remote,
    )
