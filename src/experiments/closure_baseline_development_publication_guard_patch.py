#!/usr/bin/env python
"""Validate the additive Closure V1 baseline-development authority.

E0-MQ is an implementation lock for the development-only B0/B1/B2 batch.
It cannot calibrate, create E0-M, evaluate, execute DVC, use scientific
network egress, or open outcomes after 2020-12.  The gate's only network use
is read-only remote Git alignment.  The unpublished lock keeps every execution
authorization false; only a published, exact two-file P-E0-MQ descendant can
make the one-shot B0/B1/B2 flags effective.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from src.experiments import closure_contract
from src.experiments.closure_contract import ClosureContractError, validate_json_schema


PROJECT_ROOT = Path(__file__).resolve().parents[2]

LOCK_VERSION = "closure_baseline_development_publication_guard_patch_lock_v1"
PATCH_GATE = "E0-MQ"
PATCH_ID = "baseline_development_publication_guard_authority_patch_1"
EXPERIMENT_ID = "closure_v1"
SURFACE_ID = "closure_v1_wqp_adaptive_no_current_chla"
MP_BASE_COMMIT = "a9aa51aaa1566d0b8e7154697fae69c458c5019f"
H_MP_COMMIT = "7f4099644c53e0b56d6af1adf62a0d107ade4d3a"
PATCH_BASE_COMMIT = H_MP_COMMIT
PUBLISHED_REF = "origin/main"

DEFAULT_RUNTIME_PATH = Path("configs/closure_v1/baseline_development_runtime.yaml")
DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/baseline_development_publication_guard_patch_lock.schema.json"
)
DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/baseline_development_publication_guard_patch_lock.json"
)
DEFAULT_PATCH_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/baseline_development_publication_guard_patch_lock_manifest.json"
)

PATCH_COMPONENT_ROLES = {
    DEFAULT_PATCH_LOCK_SCHEMA.as_posix(): "baseline_development_publication_guard_patch_lock_schema",
    "docs/closure_v1/E0_M_BASELINE_DEVELOPMENT_PUBLICATION_GUARD_PATCH_1.md": (
        "baseline_development_publication_guard_patch_protocol"
    ),
    "src/experiments/closure_baseline_development_publication_guard_patch.py": (
        "baseline_development_publication_guard_patch_validator"
    ),
    "src/experiments/fit_closure_baselines.py": "baseline_development_runner",
    "src/experiments/lock_closure_baseline_development_publication_guard_patch.py": (
        "baseline_development_publication_guard_patch_locker"
    ),
    "tests/test_closure_baseline_development_publication_guard_patch.py": (
        "baseline_development_publication_guard_patch_tests"
    ),
    "tests/test_fit_closure_baselines.py": "baseline_development_runner_tests",
}
PATCH_PATHS = tuple(sorted(PATCH_COMPONENT_ROLES))

MP_COMPONENT_ROLES = {
    DEFAULT_RUNTIME_PATH.as_posix(): "baseline_development_runtime",
    "configs/closure_v1/baseline_development_patch_lock.schema.json": (
        "baseline_development_patch_lock_schema"
    ),
    "docs/closure_v1/E0_M_BASELINE_DEVELOPMENT_PATCH_1.md": (
        "baseline_development_patch_protocol"
    ),
    "src/experiments/closure_baseline_development_patch.py": (
        "baseline_development_patch_validator"
    ),
    "src/experiments/fit_closure_baselines.py": "baseline_development_runner",
    "src/experiments/lock_closure_baseline_development_patch.py": (
        "baseline_development_patch_locker"
    ),
    "tests/test_closure_baseline_development_patch.py": (
        "baseline_development_patch_tests"
    ),
    "tests/test_fit_closure_baselines.py": "baseline_development_runner_tests",
}
MP_PATHS = tuple(sorted(MP_COMPONENT_ROLES))
MP_SUPERSEDED_PATHS = (
    "src/experiments/fit_closure_baselines.py",
    "tests/test_fit_closure_baselines.py",
)
MP_PRESERVED_PATHS = tuple(
    path for path in MP_PATHS if path not in MP_SUPERSEDED_PATHS
)
MP_FAILED_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/baseline_development_patch_lock.json"
)
MP_FAILED_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/baseline_development_patch_lock_manifest.json"
)
MP_FAILED_TEMP_PATHS = (
    Path(MP_FAILED_LOCK_PATH.as_posix() + ".tmp"),
    Path(MP_FAILED_MANIFEST_PATH.as_posix() + ".tmp"),
)
MP_FAILED_GUARD_PATH = Path(
    "tmp/closure_v1_e0_mp_locker/baseline_development_patch_lock.guard"
)
CURRENT_TEMP_PATHS = (
    Path(DEFAULT_PATCH_LOCK_PATH.as_posix() + ".tmp"),
    Path(DEFAULT_PATCH_MANIFEST_PATH.as_posix() + ".tmp"),
)
CURRENT_GUARD_PATH = Path(
    "tmp/closure_v1_e0_mq_locker/"
    "baseline_development_publication_guard_patch_lock.guard"
)

LEGACY_PRESERVED_RECORDS = {
    "src/experiments/baselines.py": {
        "bytes": 37940,
        "sha256": "2ab0968cf37b95082db3216b064ecca93ba3cf390ceb25071570f77be2ceb989",
    },
    "src/experiments/select_baselines.py": {
        "bytes": 23173,
        "sha256": "25594fdd0627dc692a761ef02843f7a555574b9733110d6940d90ed6c8b6ed40",
    },
    "configs/closure_v1/dvc_artifacts_post_lock.yaml": {
        "bytes": 7305,
        "sha256": "912fbdf38d1ec4cebd92dfe01e6cd760031c2c55cba3147df4707b025974ff5a",
    },
}

EXPECTED_RUNTIME_PHYSICAL_INPUT_COUNT = 40
EXPECTED_MP_PRESERVED_COUNT = 6
EXPECTED_HISTORICAL_INPUT_COUNT = 2
EXPECTED_COMPANION_INPUT_COUNT = 53

E0_M_PATHS = (
    "reports/closure_v1/00_protocol/model_lock.yaml",
    "reports/closure_v1/00_protocol/calibration_lock.yaml",
    "reports/closure_v1/00_protocol/hypothesis_registry.csv",
    "reports/closure_v1/00_protocol/locked_batch_command.txt",
)
OUTCOME_ACCESS_LOG = "reports/closure_v1/00_protocol/outcome_access_log.jsonl"

MODEL_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
CANDIDATES = ("logistic_sgd", "hist_gradient_boosting_classifier")
HORIZONS = (1, 2, 3)
TARGET_PROJECTION = (
    "source_id",
    "site_id",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
    "bloom_h",
    "target_risk_chla_h",
)
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
)
RAW_STRING_COLUMNS = (
    *RAW_PREDICTION_COLUMNS[:11],
    RAW_PREDICTION_COLUMNS[15],
    *RAW_PREDICTION_COLUMNS[17:20],
)
RAW_CANONICAL_KEY_COLUMNS = (
    "source_id",
    "site_id",
    "origin_year_month",
    "horizon_months",
    "target_year_month",
    "common_origin_id",
    "evaluation_unit_id",
)

TYPE_CHECK_COMMAND = (".venv/bin/ty", "check")
FOCUSED_TEST_COMMAND = (
    ".venv/bin/pytest",
    "tests/test_closure_baseline_development_publication_guard_patch.py",
    "tests/test_fit_closure_baselines.py",
    "-q",
)
# Frozen on the exact two-file focused suite with zero deselections/skips.
# Frozen on the exact MQ governance+runner collection with no deselections.
FOCUSED_TEST_COUNT = 69
POETRY_CHECK_COMMAND = ("poetry", "check")
PUBLICATION_GUARD_COMMAND = ("scripts/check_repo_publication_ready.sh",)
DIFF_CHECK_COMMAND = ("git", "diff", "--check")

UNPUBLISHED_AUTHORIZATIONS = {
    "baseline_one_shot_authorized": False,
    "b0_fit_authorized": False,
    "b1_execution_authorized": False,
    "b2_fit_authorized": False,
    "calibration_authorized": False,
    "e0_m_authorized": False,
    "evaluation_authorized": False,
    "e0_u_authorized": False,
    "dvc_commands_authorized": False,
    "network_authorized": False,
    "outcome_access_authorized": False,
    "future_outcomes_accessed": False,
    "effective_in_payload": False,
    "publication_required": True,
}
EFFECTIVE_AUTHORIZATIONS = {
    "baseline_one_shot_authorized": True,
    "b0_fit_authorized": True,
    "b1_execution_authorized": True,
    "b2_fit_authorized": True,
    "calibration_authorized": False,
    "e0_m_authorized": False,
    "evaluation_authorized": False,
    "e0_u_authorized": False,
    "dvc_commands_authorized": False,
    "network_authorized": False,
    "outcome_access_authorized": False,
    "future_outcomes_accessed": False,
}

PATCH_SEALS = {
    "h_scope_exact_two_modifications_five_additions": True,
    "p_scope_exact_two_additions": True,
    "legacy_baseline_scripts_unchanged": True,
    "dvc_overlay_unchanged": True,
    "target_cutoff_enforced": True,
    "calibration_labels_not_materialized": True,
    "b1_five_seed_mapping_locked": True,
    "b2_five_of_five_selection_locked": True,
    "thirty_candidate_slots_locked": True,
    "maximum_thirty_pipelines_locked": True,
    "exact_thirty_preprocessor_records_locked": True,
    "final_path_range_39_to_69_locked": True,
    "sixty_nine_potential_outputs_absent_at_lock": True,
    "manifest_written_last": True,
    "no_clobber_and_owned_inode_rollback_locked": True,
    "e0_m_absent": True,
    "outcome_access_log_absent": True,
    "future_outcomes_accessed": False,
    "h_mp_six_preserved_two_superseded": True,
    "p_mp_failed_outputs_absent": True,
    "publication_guard_exact_success_marker_locked": True,
    "companion_script_record_locked": True,
    "companion_exact_fifty_three_plus_two_locked": True,
}

PATCH_CORRECTION = {
    "classification": "publication_guard_marker_and_manifest_dialect_only",
    "scientific_runtime_contract_changed": False,
    "failed_gate": "P-E0-MP",
    "failed_command": list(PUBLICATION_GUARD_COMMAND),
    "failed_command_returncode": 0,
    "rejected_marker": "Repository publication guard passed.",
    "accepted_marker": "OK: tracked files look publication-ready.",
    "full_type_check_passed": True,
    "focused_test_count_passed": 55,
    "poetry_check_passed": True,
    "git_diff_check_reached": False,
    "payload_build_reached": False,
    "output_guard_acquired": False,
    "temporary_or_final_output_written": False,
    "p_mp_is_authority": False,
}


class BaselineDevelopmentPublicationGuardPatchError(RuntimeError):
    """Raised when E0-MQ cannot prove its exact closed authority."""


def expected_raw_prediction_contract() -> dict[str, Any]:
    columns: list[dict[str, Any]] = []
    for name in RAW_PREDICTION_COLUMNS:
        if name in RAW_STRING_COLUMNS:
            dtype = "string"
            nullable = False
        elif name == "horizon_months":
            dtype = "int16"
            nullable = False
        elif name in {"technical_seed", "model_seed", "upstream_state_seed"}:
            dtype = "int64"
            nullable = name != "technical_seed"
        elif name == "selected_family":
            dtype = "bool"
            nullable = False
        else:
            dtype = "float64"
            nullable = True
        columns.append({"name": name, "dtype": dtype, "nullable": nullable})
    return {
        "columns": columns,
        "canonical_sort_keys": [
            "model_seed_rank",
            "upstream_state_seed_rank",
            "candidate_rank",
            *RAW_CANONICAL_KEY_COLUMNS,
        ],
        "model_seed_order": list(MODEL_SEEDS),
        "candidate_order": list(CANDIDATES),
        "availability_status_values": ["success", "model_unavailable"],
        "success_score_policy": (
            "raw_score_and_probability_finite_in_closed_unit_interval"
        ),
        "unavailable_score_policy": "raw_score_and_probability_both_null",
        "B0_seed_policy": "technical_seed_only",
        "B1_seed_policy": "upstream_state_seed_only",
        "B2_seed_policy": "model_seed_only",
        "B1_probability_semantics": (
            "uncalibrated_chla_free_irc_persistence_probability"
        ),
    }


def _root(repo_root: Path | None = None) -> Path:
    return (repo_root or PROJECT_ROOT).resolve()


def _relative(path: Path, *, repo_root: Path | None = None) -> str:
    try:
        return path.resolve().relative_to(_root(repo_root)).as_posix()
    except ValueError as exc:
        raise BaselineDevelopmentPublicationGuardPatchError(f"Path escapes repository: {path}") from exc


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
        raise BaselineDevelopmentPublicationGuardPatchError(
            f"Required regular file cannot be opened safely: {_relative(absolute, repo_root=repo_root)}"
        ) from exc
    try:
        observed = os.fstat(descriptor)
        if not stat.S_ISREG(observed.st_mode):
            raise BaselineDevelopmentPublicationGuardPatchError(
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
        raise BaselineDevelopmentPublicationGuardPatchError(f"{context} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise BaselineDevelopmentPublicationGuardPatchError(f"{context} must be a JSON object")
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


def preflight_baseline_development_publication_guard_patch_schema(
    schema_path: Path = DEFAULT_PATCH_LOCK_SCHEMA,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Validate the physical schema before guards, commands, or data reads."""
    if schema_path != DEFAULT_PATCH_LOCK_SCHEMA:
        raise BaselineDevelopmentPublicationGuardPatchError("E0-MQ requires the closed default schema path")
    schema = _load_regular_json(
        schema_path,
        context="E0-MQ lock schema",
        repo_root=repo_root,
    )
    minimum_count = _keyword_occurrences(schema, "minimum")
    format_count = _keyword_occurrences(schema, "format")
    if minimum_count or format_count:
        raise BaselineDevelopmentPublicationGuardPatchError(
            "E0-MQ schema uses unsupported keywords: "
            f"minimum={minimum_count}, format={format_count}"
        )
    validator = getattr(closure_contract, "_assert_supported_json_schema", None)
    if not callable(validator):
        raise BaselineDevelopmentPublicationGuardPatchError(
            "Closure JSON-schema definition validator is unavailable"
        )
    try:
        validator(schema)
    except ClosureContractError as exc:
        raise BaselineDevelopmentPublicationGuardPatchError(str(exc)) from exc
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


def load_and_validate_baseline_development_runtime(
    runtime_path: Path = DEFAULT_RUNTIME_PATH,
    *,
    repo_root: Path | None = None,
    verify_physical_pins: bool = True,
) -> dict[str, Any]:
    """Load the additive runtime and enforce its scientific/operational seals."""
    if runtime_path != DEFAULT_RUNTIME_PATH:
        raise BaselineDevelopmentPublicationGuardPatchError("E0-MQ requires the closed default runtime path")
    try:
        value = yaml.safe_load(_read_regular_bytes(runtime_path, repo_root=repo_root))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise BaselineDevelopmentPublicationGuardPatchError("E0-MQ runtime is not valid YAML") from exc
    if not isinstance(value, dict):
        raise BaselineDevelopmentPublicationGuardPatchError("E0-MQ runtime must be a mapping")
    expected_identity = {
        "schema_version": "closure_baseline_development_runtime_v1",
        "experiment_id": EXPERIMENT_ID,
        "surface_id": SURFACE_ID,
        "status": "ready_to_lock",
        "gate": "E0-MP",
        "patch_id": "baseline_development_authority_patch_1",
        "patch_base_commit": MP_BASE_COMMIT,
    }
    for key, expected in expected_identity.items():
        if value.get(key) != expected:
            raise BaselineDevelopmentPublicationGuardPatchError(f"Runtime identity drifted: {key}")
    roles = value.get("roles")
    if not isinstance(roles, Mapping) or (
        roles.get("training_target_end") != "2018-12"
        or roles.get("model_selection_origin_start") != "2019-01"
        or roles.get("model_selection_target_end") != "2020-12"
        or roles.get("calibration_labels_materialized_by_this_runner") is not False
        or roles.get("origin_and_target_must_share_role") is not True
        or roles.get("holdout_locations_excluded") is not True
        or "origin_year_month<=2020-12" not in str(roles.get("target_scanner_predicate"))
        or "target_year_month<=2020-12" not in str(roles.get("target_scanner_predicate"))
    ):
        raise BaselineDevelopmentPublicationGuardPatchError("Runtime target cutoff/role contract drifted")
    denominators = value.get("denominators")
    if not isinstance(denominators, Mapping) or (
        denominators.get("common_origin_rows") != 29196
        or denominators.get("intent_origins") != 9732
        or denominators.get("development_locations") != 353
        or denominators.get("complete_target_origins_by_role")
        != {"training": 5932, "model_selection": 658, "calibration_threshold": 224}
        or denominators.get("horizons_months") != [1, 2, 3]
    ):
        raise BaselineDevelopmentPublicationGuardPatchError("Runtime denominators drifted")
    seeds = value.get("seeds")
    if not isinstance(seeds, Mapping) or (
        tuple(seeds.get("ordered_model_seeds", ())) != MODEL_SEEDS
        or seeds.get("technical_seed") != 1729
        or seeds.get("best_seed_selection") != "forbidden"
        or seeds.get("pooling_as_independent_observations") != "forbidden"
    ):
        raise BaselineDevelopmentPublicationGuardPatchError("Runtime seed contract drifted")
    models = value.get("models")
    if not isinstance(models, Mapping):
        raise BaselineDevelopmentPublicationGuardPatchError("Runtime model contract is absent")
    b0 = models.get("B0")
    b1 = models.get("B1")
    b2 = models.get("B2")
    if not all(isinstance(item, Mapping) for item in (b0, b1, b2)):
        raise BaselineDevelopmentPublicationGuardPatchError("Runtime B0/B1/B2 mappings are absent")
    assert isinstance(b0, Mapping) and isinstance(b1, Mapping) and isinstance(b2, Mapping)
    if (
        b0.get("fit_role") != "training"
        or b0.get("fit_complete_target_origins_only") is not True
        or b0.get("prediction_rows") != 29196
        or b0.get("calibration_authorized") is not False
    ):
        raise BaselineDevelopmentPublicationGuardPatchError("Runtime B0 contract drifted")
    if (
        tuple(b1.get("upstream_state_seeds", ())) != MODEL_SEEDS
        or b1.get("origin_state_columns")
        != ["yN_adaptive", "yF_adaptive", "yT_no_chla_adaptive"]
        or b1.get("raw_score_formula")
        != "clip_0_1_of_yN_plus_1_minus_yF_plus_yT_no_chla_divided_by_3"
        or b1.get("score_semantics")
        != "uncalibrated_chla_free_irc_persistence_probability"
        or b1.get("predicted_bloom_probability") != "same_as_raw_score"
        or b1.get("calibration_applied") is not False
        or b1.get("fallback") != "forbidden"
        or b1.get("missing_origin_state_status") != "model_unavailable"
        or b1.get("total_prediction_rows") != 145980
    ):
        raise BaselineDevelopmentPublicationGuardPatchError("Runtime B1 contract drifted")
    selection = b2.get("selection")
    calendar_formula = b2.get("calendar_formula")
    preprocessing = b2.get("preprocessing")
    physical_features = b2.get("physical_feature_columns")
    derived_features = b2.get("derived_calendar_columns")
    if not isinstance(selection, Mapping) or (
        b2.get("exact_feature_count") != 42
        or not isinstance(physical_features, list)
        or len(physical_features) != 38
        or len(set(physical_features)) != 38
        or any(
            token in "\n".join(str(column).lower() for column in physical_features)
            for token in ("chla", "chlorophyll", "risk_chla")
        )
        or derived_features
        != [
            "season_sin_annual",
            "season_cos_annual",
            "season_sin_semiannual",
            "season_cos_semiannual",
        ]
        or b2.get("candidate_slot_count") != 30
        or b2.get("maximum_pipeline_count") != 30
        or b2.get("exact_preprocessor_record_count") != 30
        or b2.get("total_candidate_prediction_rows") != 291960
        or not isinstance(calendar_formula, Mapping)
        or calendar_formula.get("month_angle_float64") != "2*pi*(month-1)/12"
        or calendar_formula.get("derivation_output_dtype") != "float32"
        or calendar_formula.get("model_matrix_dtype") != "float64"
        or not isinstance(preprocessing, Mapping)
        or preprocessing.get("median_and_model_matrix_dtype") != "float64"
        or selection.get("required_finite_seed_count") != 5
        or selection.get("brier_tolerance") != 0.001
        or selection.get("final_tie_break") != "logistic_sgd"
    ):
        raise BaselineDevelopmentPublicationGuardPatchError("Runtime B2 contract drifted")
    outputs = value.get("outputs")
    if not isinstance(outputs, Mapping) or (
        outputs.get("exact_raw_prediction_rows") != 467136
        or outputs.get("minimum_final_path_count") != 39
        or outputs.get("maximum_final_path_count") != 69
        or outputs.get("raw_prediction_contract")
        != expected_raw_prediction_contract()
        or outputs.get("manifest_written_last") is not True
    ):
        raise BaselineDevelopmentPublicationGuardPatchError("Runtime output contract drifted")
    reproducibility = value.get("reproducibility")
    if reproducibility != {
        "execution_device": "cpu",
        "threadpool_limit": 1,
        "dependency_files": ["pyproject.toml", "poetry.lock"],
        "runtime_versions_recorded_in_manifest": True,
    }:
        raise BaselineDevelopmentPublicationGuardPatchError("Runtime reproducibility contract drifted")
    publication = outputs.get("publication")
    if not isinstance(publication, Mapping) or any(
        publication.get(key) is not True
        for key in (
            "parent_walk_no_follow",
            "no_clobber",
            "hardlink_publication",
            "rollback_owned_inode_only",
        )
    ):
        raise BaselineDevelopmentPublicationGuardPatchError("Runtime atomic publication contract drifted")
    authorizations = value.get("authorizations")
    if not isinstance(authorizations, Mapping) or any(
        authorizations.get(key) is not False
        for key in (
            "baseline_one_shot_authorized",
            "b0_fit_authorized",
            "b1_execution_authorized",
            "b2_fit_authorized",
            "calibration_authorized",
            "e0_m_authorized",
            "evaluation_authorized",
            "e0_u_authorized",
            "dvc_commands_authorized",
            "network_authorized",
            "outcome_access_authorized",
            "future_outcomes_accessed",
        )
    ):
        raise BaselineDevelopmentPublicationGuardPatchError("Runtime authorizations are not all closed")
    dvc = value.get("dvc")
    if not isinstance(dvc, Mapping) or (
        dvc.get("authorized_during_h_or_p") is not False
        or dvc.get("authorized_during_one_shot") is not False
        or dvc.get("post_audit_registration_required") is not True
    ):
        raise BaselineDevelopmentPublicationGuardPatchError("Runtime DVC contract drifted")
    bundles = value.get("upstream_anfis_bundles")
    if not isinstance(bundles, list) or [item.get("base_seed") for item in bundles] != list(MODEL_SEEDS):
        raise BaselineDevelopmentPublicationGuardPatchError("Runtime ANFIS bundle order drifted")
    if verify_physical_pins:
        _verify_runtime_physical_pins(value, repo_root=repo_root)
    return value


def _verify_runtime_physical_pins(
    runtime: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    authority = runtime.get("authority")
    if not isinstance(authority, Mapping):
        raise BaselineDevelopmentPublicationGuardPatchError("Runtime authority mapping is absent")
    for role, expected in authority.items():
        if not isinstance(expected, Mapping) or "path" not in expected:
            continue
        record = _file_record(Path(str(expected["path"])), role=str(role), repo_root=repo_root)
        if record["sha256"] != expected.get("sha256") or (
            "bytes" in expected and record["bytes"] != expected.get("bytes")
        ):
            raise BaselineDevelopmentPublicationGuardPatchError(f"Runtime authority pin drifted: {role}")
        records.append(record)
    bundles = runtime.get("upstream_anfis_bundles")
    assert isinstance(bundles, list)
    for bundle in bundles:
        seed = bundle.get("base_seed")
        for role in ("state", "pointer", "manifest"):
            expected = bundle.get(role)
            if not isinstance(expected, Mapping):
                raise BaselineDevelopmentPublicationGuardPatchError(f"ANFIS {seed} {role} pin is absent")
            record = _file_record(
                Path(str(expected["path"])),
                role=f"anfis_{seed}_{role}",
                repo_root=repo_root,
            )
            if record["bytes"] != expected.get("bytes") or record["sha256"] != expected.get("sha256"):
                raise BaselineDevelopmentPublicationGuardPatchError(f"ANFIS {seed} {role} pin drifted")
            records.append(record)
    records.sort(key=lambda item: str(item["path"]))
    paths = [str(record["path"]) for record in records]
    if (
        len(records) != EXPECTED_RUNTIME_PHYSICAL_INPUT_COUNT
        or len(set(paths)) != EXPECTED_RUNTIME_PHYSICAL_INPUT_COUNT
    ):
        raise BaselineDevelopmentPublicationGuardPatchError(
            "Runtime physical authority must contain exactly 40 unique inputs"
        )
    return records


def baseline_final_paths(runtime: Mapping[str, Any]) -> tuple[str, ...]:
    outputs = runtime.get("outputs")
    if not isinstance(outputs, Mapping):
        raise BaselineDevelopmentPublicationGuardPatchError("Runtime outputs mapping is absent")
    raw = outputs.get("raw_score_parquets")
    light = outputs.get("light_bundle")
    if not isinstance(raw, Mapping) or not isinstance(light, Mapping):
        raise BaselineDevelopmentPublicationGuardPatchError("Runtime output maps are absent")
    paths = [str(raw[key]) for key in ("B0", "B1", "B2")]
    pipeline_template = str(outputs.get("b2_pipeline_template"))
    preprocessor_template = str(outputs.get("b2_preprocessor_template"))
    for seed in MODEL_SEEDS:
        for candidate in CANDIDATES:
            for horizon in HORIZONS:
                paths.append(
                    pipeline_template.format(
                        model_seed=seed,
                        candidate=candidate,
                        horizon=horizon,
                    )
                )
                paths.append(
                    preprocessor_template.format(
                        model_seed=seed,
                        candidate=candidate,
                        horizon=horizon,
                    )
                )
    paths.extend(str(light[key]) for key in (
        "model_specs",
        "metrics",
        "selection",
        "lineage_audit",
        "report",
        "manifest",
    ))
    result = tuple(paths)
    if len(result) != 69 or len(set(result)) != 69:
        raise BaselineDevelopmentPublicationGuardPatchError("Baseline final namespace is not exactly 69 unique paths")
    return result


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def baseline_output_namespace_absence(
    runtime: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = _root(repo_root)
    finals = baseline_final_paths(runtime)
    temporaries = tuple(f"{path}.tmp" for path in finals)
    publication = runtime["outputs"]["publication"]
    guard = str(publication["guard_path"])
    dvc = runtime.get("dvc")
    if not isinstance(dvc, Mapping):
        raise BaselineDevelopmentPublicationGuardPatchError("Runtime DVC namespace is absent")
    future_pointers = tuple(str(path) for path in dvc.get("future_pointer_paths", ()))
    if len(future_pointers) != 3 or len(set(future_pointers)) != 3:
        raise BaselineDevelopmentPublicationGuardPatchError("Future raw-score DVC pointer namespace drifted")
    present_finals = [path for path in finals if _lexists(root / path)]
    present_temporaries = [path for path in temporaries if _lexists(root / path)]
    present_pointers = [path for path in future_pointers if _lexists(root / path)]
    pointer_temporaries = tuple(f"{path}.tmp" for path in future_pointers)
    present_pointer_temporaries = [
        path for path in pointer_temporaries if _lexists(root / path)
    ]
    guard_present = _lexists(root / guard)
    if (
        present_finals
        or present_temporaries
        or present_pointers
        or present_pointer_temporaries
        or guard_present
    ):
        raise BaselineDevelopmentPublicationGuardPatchError(
            "Baseline output namespace is not empty: "
            f"finals={present_finals}, temporaries={present_temporaries}, "
            f"pointers={present_pointers}, pointer_temporaries="
            f"{present_pointer_temporaries}, guard={guard_present}"
        )
    return {
        "final_count": 69,
        "final_paths": list(finals),
        "final_paths_sha256": _path_digest(finals),
        "all_final_absent": True,
        "temporary_count": 69,
        "temporary_paths_sha256": _path_digest(temporaries),
        "all_temporary_absent": True,
        "future_pointer_count": 3,
        "future_pointer_paths": list(future_pointers),
        "future_pointer_paths_sha256": _path_digest(future_pointers),
        "all_future_pointers_absent": True,
        "future_pointer_temporary_count": 3,
        "future_pointer_temporary_paths_sha256": _path_digest(pointer_temporaries),
        "all_future_pointer_temporaries_absent": True,
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
        raise BaselineDevelopmentPublicationGuardPatchError(
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
        raise BaselineDevelopmentPublicationGuardPatchError("Remote main observation is not unique")
    fields = lines[0].split("\t")
    if (
        len(fields) != 2
        or fields[1] != "refs/heads/main"
        or len(fields[0]) != 40
        or any(character not in "0123456789abcdef" for character in fields[0])
    ):
        raise BaselineDevelopmentPublicationGuardPatchError("Remote main observation is malformed")
    return fields[0]


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
            raise BaselineDevelopmentPublicationGuardPatchError(f"Unsupported H diff entry: {line}")
        entries.append({"status": fields[0], "path": fields[1]})
    return entries


def _single_parent(commit: str, *, repo_root: Path | None = None) -> str:
    fields = _git("rev-list", "--parents", "-n", "1", commit, repo_root=repo_root).split()
    if len(fields) != 2 or fields[0] != commit:
        raise BaselineDevelopmentPublicationGuardPatchError(
            f"Commit is not a direct non-merge child: {commit}"
        )
    return fields[1]


def _validate_h_component_records(h_patch: Mapping[str, Any]) -> list[dict[str, Any]]:
    paths = h_patch.get("paths")
    components = h_patch.get("components")
    if (
        h_patch.get("base_commit") != PATCH_BASE_COMMIT
        or h_patch.get("added_count") != 5
        or h_patch.get("modified_count") != 2
        or paths != list(PATCH_PATHS)
        or not isinstance(components, list)
    ):
        raise BaselineDevelopmentPublicationGuardPatchError("E0-MQ H scope drifted")
    if len(components) != len(PATCH_PATHS):
        raise BaselineDevelopmentPublicationGuardPatchError("E0-MQ H component count drifted")
    normalized: list[dict[str, Any]] = []
    for index, path in enumerate(PATCH_PATHS):
        candidate = components[index]
        if not isinstance(candidate, Mapping):
            raise BaselineDevelopmentPublicationGuardPatchError("E0-MQ H component is not a mapping")
        record = dict(candidate)
        if (
            set(record) != {"path", "role", "bytes", "sha256"}
            or record.get("path") != path
            or record.get("role") != PATCH_COMPONENT_ROLES[path]
            or not isinstance(record.get("bytes"), int)
            or int(record["bytes"]) < 1
            or not isinstance(record.get("sha256"), str)
            or len(str(record["sha256"])) != 64
        ):
            raise BaselineDevelopmentPublicationGuardPatchError(
                f"E0-MQ H component binding drifted: {path}"
            )
        normalized.append(record)
    component_paths = [str(record["path"]) for record in normalized]
    if len(set(component_paths)) != len(PATCH_PATHS):
        raise BaselineDevelopmentPublicationGuardPatchError("E0-MQ H components contain duplicates")
    if h_patch.get("paths_sha256") != _path_digest(PATCH_PATHS) or h_patch.get(
        "components_sha256"
    ) != _record_digest(normalized):
        raise BaselineDevelopmentPublicationGuardPatchError("E0-MQ H digests drifted")
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
        raise BaselineDevelopmentPublicationGuardPatchError(
            f"E0-MQ cannot reconstruct H blob: {path}"
        )
    return {
        "path": path,
        "role": role,
        "bytes": len(result.stdout),
        "sha256": _sha256_bytes(result.stdout),
    }


def _historical_mp_record(
    path: str,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    role = {
        "src/experiments/fit_closure_baselines.py": (
            "historical_baseline_development_runner"
        ),
        "tests/test_fit_closure_baselines.py": (
            "historical_baseline_development_runner_tests"
        ),
    }[path]
    return {
        **_git_blob_record(H_MP_COMMIT, path, role=role, repo_root=repo_root),
        "commit": H_MP_COMMIT,
        "hash_source": "git_blob_at_commit",
    }


def _historical_mp_authority(
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    if _single_parent(H_MP_COMMIT, repo_root=repo_root) != MP_BASE_COMMIT:
        raise BaselineDevelopmentPublicationGuardPatchError(
            "Published H-E0-MP parent drifted"
        )
    entries = _observed_diff_entries(MP_BASE_COMMIT, H_MP_COMMIT, repo_root=repo_root)
    expected = [{"status": "A", "path": path} for path in MP_PATHS]
    if sorted(entries, key=lambda item: item["path"]) != expected:
        raise BaselineDevelopmentPublicationGuardPatchError(
            "Published H-E0-MP is not exactly eight additions"
        )
    git_records = {
        path: _git_blob_record(
            H_MP_COMMIT,
            path,
            role=MP_COMPONENT_ROLES[path],
            repo_root=repo_root,
        )
        for path in MP_PATHS
    }
    preserved: list[dict[str, Any]] = []
    for path in MP_PRESERVED_PATHS:
        observed = _file_record(
            Path(path),
            role=MP_COMPONENT_ROLES[path],
            repo_root=repo_root,
        )
        if observed != git_records[path]:
            raise BaselineDevelopmentPublicationGuardPatchError(
                f"Preserved H-E0-MP component drifted: {path}"
            )
        preserved.append(observed)
    historical = [
        _historical_mp_record(path, repo_root=repo_root)
        for path in MP_SUPERSEDED_PATHS
    ]
    if (
        len(preserved) != EXPECTED_MP_PRESERVED_COUNT
        or len(historical) != EXPECTED_HISTORICAL_INPUT_COUNT
        or len({record["path"] for record in (*preserved, *historical)}) != len(MP_PATHS)
    ):
        raise BaselineDevelopmentPublicationGuardPatchError(
            "H-E0-MP preserved/historical partition drifted"
        )
    return {
        "base_commit": MP_BASE_COMMIT,
        "h_commit": H_MP_COMMIT,
        "path_count": len(MP_PATHS),
        "paths": list(MP_PATHS),
        "paths_sha256": _path_digest(MP_PATHS),
        "preserved_count": EXPECTED_MP_PRESERVED_COUNT,
        "preserved_records": preserved,
        "preserved_records_sha256": _record_digest(preserved),
        "superseded_count": EXPECTED_HISTORICAL_INPUT_COUNT,
        "historical_records": historical,
        "historical_records_sha256": _record_digest(historical),
        "git_authority_verified": True,
        "effective_loader_called": False,
    }


def _reconstruct_h_components(
    payload: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> list[dict[str, Any]]:
    repository = payload.get("repository")
    h_patch = payload.get("h_patch")
    if not isinstance(repository, Mapping) or not isinstance(h_patch, Mapping):
        raise BaselineDevelopmentPublicationGuardPatchError("E0-MQ H authority is absent")
    h_head = repository.get("head")
    if not isinstance(h_head, str) or len(h_head) != 40:
        raise BaselineDevelopmentPublicationGuardPatchError("E0-MQ H commit is malformed")
    if _single_parent(h_head, repo_root=repo_root) != PATCH_BASE_COMMIT:
        raise BaselineDevelopmentPublicationGuardPatchError("E0-MQ H parent drifted")
    entries = _observed_diff_entries(PATCH_BASE_COMMIT, h_head, repo_root=repo_root)
    expected_entries = [
        {
            "status": "M" if path in MP_SUPERSEDED_PATHS else "A",
            "path": path,
        }
        for path in PATCH_PATHS
    ]
    if sorted(entries, key=lambda item: item["path"]) != expected_entries:
        raise BaselineDevelopmentPublicationGuardPatchError(
            "E0-MQ H commit is not exactly two modifications and five additions"
        )
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
    if reconstructed != locked:
        raise BaselineDevelopmentPublicationGuardPatchError("E0-MQ H Git blobs differ from the lock")
    current = [
        _file_record(
            Path(path),
            role=PATCH_COMPONENT_ROLES[path],
            repo_root=repo_root,
        )
        for path in PATCH_PATHS
    ]
    if current != locked:
        raise BaselineDevelopmentPublicationGuardPatchError("E0-MQ H files drifted after publication")
    return reconstructed


def collect_baseline_development_publication_guard_patch_prelock_state(
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Collect exact H state, including the required read-only remote check."""
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
        raise BaselineDevelopmentPublicationGuardPatchError("Published H topology/ref alignment drifted")
    if _git("status", "--porcelain=v1", "--untracked-files=all", repo_root=root):
        raise BaselineDevelopmentPublicationGuardPatchError("E0-MQ H repository must be clean")
    entries = _observed_diff_entries(PATCH_BASE_COMMIT, head, repo_root=root)
    expected_entries = [
        {
            "status": "M" if path in MP_SUPERSEDED_PATHS else "A",
            "path": path,
        }
        for path in PATCH_PATHS
    ]
    if sorted(entries, key=lambda item: item["path"]) != expected_entries:
        raise BaselineDevelopmentPublicationGuardPatchError("H-E0-MQ is not exactly two modifications and five additions")
    components = [
        _file_record(Path(path), role=PATCH_COMPONENT_ROLES[path], repo_root=root)
        for path in PATCH_PATHS
    ]
    mp_authority = _historical_mp_authority(repo_root=root)
    runtime = load_and_validate_baseline_development_runtime(
        repo_root=root,
        verify_physical_pins=False,
    )
    physical_inputs = _verify_runtime_physical_pins(runtime, repo_root=root)
    namespace = baseline_output_namespace_absence(runtime, repo_root=root)
    for path, expected in LEGACY_PRESERVED_RECORDS.items():
        observed = _file_record(Path(path), role="preserved", repo_root=root)
        if observed["bytes"] != expected["bytes"] or observed["sha256"] != expected["sha256"]:
            raise BaselineDevelopmentPublicationGuardPatchError(f"Preserved historical path drifted: {path}")
    e0_m_present = [path for path in E0_M_PATHS if _lexists(root / path)]
    outcome_present = _lexists(root / OUTCOME_ACCESS_LOG)
    if e0_m_present or outcome_present:
        raise BaselineDevelopmentPublicationGuardPatchError("E0-M or outcome-access log exists before E0-MQ")
    runtime_record = next(
        record
        for record in mp_authority["preserved_records"]
        if record["path"] == DEFAULT_RUNTIME_PATH.as_posix()
    )
    forbidden_patch_paths = (
        MP_FAILED_LOCK_PATH,
        MP_FAILED_MANIFEST_PATH,
        *MP_FAILED_TEMP_PATHS,
        MP_FAILED_GUARD_PATH,
        DEFAULT_PATCH_LOCK_PATH,
        DEFAULT_PATCH_MANIFEST_PATH,
        *CURRENT_TEMP_PATHS,
        CURRENT_GUARD_PATH,
    )
    present_patch_paths = [
        path.as_posix() for path in forbidden_patch_paths if _lexists(root / path)
    ]
    if present_patch_paths:
        raise BaselineDevelopmentPublicationGuardPatchError(
            f"E0-MP/E0-MQ patch output namespace is not empty: {present_patch_paths}"
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
            "added_count": 5,
            "modified_count": 2,
            "paths": list(PATCH_PATHS),
            "paths_sha256": _path_digest(PATCH_PATHS),
            "components": components,
            "components_sha256": _record_digest(components),
        },
        "mp_authority": mp_authority,
        "correction": dict(PATCH_CORRECTION),
        "runtime_contract": {
            "record": runtime_record,
            "schema_subset_verified": True,
            "pins_verified": True,
            "target_cutoff": "2020-12",
            "target_projection": list(TARGET_PROJECTION),
            "raw_prediction_contract": expected_raw_prediction_contract(),
            "b1_seed_count": 5,
            "candidate_slot_count": 30,
            "maximum_pipeline_count": 30,
            "exact_preprocessor_record_count": 30,
            "minimum_final_path_count": 39,
            "maximum_final_path_count": 69,
            "physical_input_count": EXPECTED_RUNTIME_PHYSICAL_INPUT_COUNT,
            "physical_inputs": physical_inputs,
            "physical_inputs_sha256": _record_digest(physical_inputs),
        },
        "prelock": {
            "output_namespace": namespace,
            "e0_m_paths": list(E0_M_PATHS),
            "all_e0_m_paths_absent": True,
            "outcome_access_log_path": OUTCOME_ACCESS_LOG,
            "outcome_access_log_absent": True,
            "dvc_commands_run": False,
            "network_commands_run": True,
            "data_execution_run": False,
            "auditor_run": False,
            "future_outcomes_accessed": False,
            "p_mp_lock_absent": True,
            "p_mp_companion_absent": True,
            "p_mp_temporaries_absent": True,
            "p_mp_guard_absent": True,
            "p_mq_outputs_absent": True,
            "p_mq_temporaries_absent": True,
            "p_mq_guard_absent": True,
        },
    }


def build_baseline_development_publication_guard_patch_lock_payload(
    prelock: Mapping[str, Any],
    verification: Mapping[str, Any],
    *,
    created_at_utc: str,
) -> dict[str, Any]:
    return {
        "lock_version": LOCK_VERSION,
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "experiment_id": EXPERIMENT_ID,
        "surface_id": SURFACE_ID,
        "status": "locked_unpublished",
        "created_at_utc": created_at_utc,
        "repository": dict(prelock["repository"]),
        "correction": dict(prelock["correction"]),
        "mp_authority": dict(prelock["mp_authority"]),
        "h_patch": dict(prelock["h_patch"]),
        "runtime_contract": dict(prelock["runtime_contract"]),
        "prelock": dict(prelock["prelock"]),
        "verification": dict(verification),
        "authorizations": dict(UNPUBLISHED_AUTHORIZATIONS),
        "seals": dict(PATCH_SEALS),
    }


def _validate_timestamp(value: Any) -> None:
    if not isinstance(value, str):
        raise BaselineDevelopmentPublicationGuardPatchError("Lock timestamp must be a string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BaselineDevelopmentPublicationGuardPatchError("Lock timestamp is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BaselineDevelopmentPublicationGuardPatchError("Lock timestamp must include timezone")


def _validate_repository_binding(repository: Any) -> None:
    if not isinstance(repository, Mapping):
        raise BaselineDevelopmentPublicationGuardPatchError(
            "E0-MQ repository binding is absent"
        )
    head = repository.get("head")
    if (
        not isinstance(head, str)
        or len(head) != 40
        or repository.get("parent") != PATCH_BASE_COMMIT
        or repository.get("branch") != "main"
        or repository.get("tracking_ref") != PUBLISHED_REF
        or repository.get("tracking_head") != head
        or repository.get("remote_head") != head
        or repository.get("remote_observation_mode")
        != "live_remote_main_verified"
        or repository.get("worktree_status") != "clean"
    ):
        raise BaselineDevelopmentPublicationGuardPatchError(
            "E0-MQ repository/ref binding drifted"
        )


def _require_evidence_command(
    value: Any,
    command: Sequence[str],
    *,
    context: str,
    exact_stdout: str | None = None,
) -> None:
    if not isinstance(value, Mapping) or value.get("command") != list(command):
        raise BaselineDevelopmentPublicationGuardPatchError(
            f"E0-MQ {context} command drifted"
        )
    if value.get("returncode") != 0:
        raise BaselineDevelopmentPublicationGuardPatchError(
            f"E0-MQ {context} return code drifted"
        )
    empty_sha = _sha256_bytes(b"")
    if value.get("stderr_sha256") != empty_sha or value.get("stderr_line_count") != 0:
        raise BaselineDevelopmentPublicationGuardPatchError(
            f"E0-MQ {context} stderr evidence drifted"
        )
    if exact_stdout is not None and (
        value.get("stdout_sha256") != _sha256_bytes(exact_stdout.encode("utf-8"))
        or value.get("stdout_line_count") != len(exact_stdout.splitlines())
    ):
        raise BaselineDevelopmentPublicationGuardPatchError(
            f"E0-MQ {context} stdout evidence drifted"
        )


def _validate_verification_binding(value: Any, *, repo_root: Path | None = None) -> None:
    if not isinstance(value, Mapping):
        raise BaselineDevelopmentPublicationGuardPatchError(
            "E0-MQ verification evidence is absent"
        )
    expected_keys = {
        "schema_preflight",
        "full_type_check",
        "focused_tests",
        "poetry_check",
        "publication_guard",
        "git_diff_check",
    }
    if set(value) != expected_keys or value.get("schema_preflight") != (
        preflight_baseline_development_publication_guard_patch_schema(
            repo_root=repo_root
        )
    ):
        raise BaselineDevelopmentPublicationGuardPatchError(
            "E0-MQ schema/verification binding drifted"
        )
    _require_evidence_command(
        value.get("full_type_check"),
        TYPE_CHECK_COMMAND,
        context="full type check",
        exact_stdout="All checks passed!\n",
    )
    focused = value.get("focused_tests")
    _require_evidence_command(
        focused,
        FOCUSED_TEST_COMMAND,
        context="focused tests",
    )
    if not isinstance(focused, Mapping) or (
        focused.get("test_count") != FOCUSED_TEST_COUNT
        or focused.get("skipped_count") != 0
        or focused.get("deselected_count") != 0
    ):
        raise BaselineDevelopmentPublicationGuardPatchError(
            "E0-MQ focused-test evidence drifted"
        )
    _require_evidence_command(
        value.get("poetry_check"),
        POETRY_CHECK_COMMAND,
        context="Poetry check",
        exact_stdout="All set!\n",
    )
    _require_evidence_command(
        value.get("publication_guard"),
        PUBLICATION_GUARD_COMMAND,
        context="publication guard",
        exact_stdout=(
            "Checking tracked files before publication...\n"
            "OK: tracked files look publication-ready.\n"
        ),
    )
    _require_evidence_command(
        value.get("git_diff_check"),
        DIFF_CHECK_COMMAND,
        context="git diff check",
        exact_stdout="",
    )


def validate_baseline_development_publication_guard_patch_lock_payload(
    payload: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    schema = _load_regular_json(
        DEFAULT_PATCH_LOCK_SCHEMA,
        context="E0-MQ lock schema",
        repo_root=repo_root,
    )
    try:
        validate_json_schema(payload, schema)
    except ClosureContractError as exc:
        raise BaselineDevelopmentPublicationGuardPatchError(str(exc)) from exc
    _validate_timestamp(payload.get("created_at_utc"))
    _validate_repository_binding(payload.get("repository"))
    _validate_verification_binding(payload.get("verification"), repo_root=repo_root)
    if payload.get("authorizations") != UNPUBLISHED_AUTHORIZATIONS:
        raise BaselineDevelopmentPublicationGuardPatchError("Unpublished E0-MQ authorizations drifted")
    if payload.get("seals") != PATCH_SEALS:
        raise BaselineDevelopmentPublicationGuardPatchError("E0-MQ seals drifted")
    if payload.get("correction") != PATCH_CORRECTION:
        raise BaselineDevelopmentPublicationGuardPatchError("E0-MQ correction drifted")
    mp_authority = payload.get("mp_authority")
    if not isinstance(mp_authority, Mapping) or dict(mp_authority) != _historical_mp_authority(
        repo_root=repo_root
    ):
        raise BaselineDevelopmentPublicationGuardPatchError(
            "E0-MQ historical H-E0-MP authority drifted"
        )
    h_patch = payload.get("h_patch")
    if not isinstance(h_patch, Mapping):
        raise BaselineDevelopmentPublicationGuardPatchError("E0-MQ H payload is absent")
    _validate_h_component_records(h_patch)
    runtime_contract = payload.get("runtime_contract")
    if not isinstance(runtime_contract, Mapping):
        raise BaselineDevelopmentPublicationGuardPatchError("E0-MQ runtime lock binding is absent")
    expected_runtime_record = next(
        record
        for record in mp_authority["preserved_records"]
        if record["path"] == DEFAULT_RUNTIME_PATH.as_posix()
    )
    if runtime_contract.get("record") != expected_runtime_record:
        raise BaselineDevelopmentPublicationGuardPatchError(
            "E0-MQ runtime file record drifted"
        )
    physical_inputs = runtime_contract.get("physical_inputs")
    if (
        not isinstance(physical_inputs, list)
        or len(physical_inputs) != EXPECTED_RUNTIME_PHYSICAL_INPUT_COUNT
        or len({str(record.get("path")) for record in physical_inputs if isinstance(record, Mapping)})
        != EXPECTED_RUNTIME_PHYSICAL_INPUT_COUNT
        or runtime_contract.get("physical_input_count")
        != EXPECTED_RUNTIME_PHYSICAL_INPUT_COUNT
        or runtime_contract.get("physical_inputs_sha256")
        != _record_digest(physical_inputs)
    ):
        raise BaselineDevelopmentPublicationGuardPatchError("E0-MQ physical input binding drifted")
    runtime = load_and_validate_baseline_development_runtime(
        repo_root=repo_root,
        verify_physical_pins=False,
    )
    prelock = payload.get("prelock")
    expected_namespace = baseline_output_namespace_absence(runtime, repo_root=repo_root)
    expected_prelock = {
        "output_namespace": expected_namespace,
        "e0_m_paths": list(E0_M_PATHS),
        "all_e0_m_paths_absent": True,
        "outcome_access_log_path": OUTCOME_ACCESS_LOG,
        "outcome_access_log_absent": True,
        "dvc_commands_run": False,
        "network_commands_run": True,
        "data_execution_run": False,
        "auditor_run": False,
        "future_outcomes_accessed": False,
        "p_mp_lock_absent": True,
        "p_mp_companion_absent": True,
        "p_mp_temporaries_absent": True,
        "p_mp_guard_absent": True,
        "p_mq_outputs_absent": True,
        "p_mq_temporaries_absent": True,
        "p_mq_guard_absent": True,
    }
    if prelock != expected_prelock:
        raise BaselineDevelopmentPublicationGuardPatchError("E0-MQ output namespace drifted")
    return dict(payload)


def _expected_companion(
    payload: Mapping[str, Any],
    lock_record: Mapping[str, Any],
) -> dict[str, Any]:
    h_patch = payload.get("h_patch")
    mp_authority = payload.get("mp_authority")
    runtime_contract = payload.get("runtime_contract")
    if (
        not isinstance(h_patch, Mapping)
        or not isinstance(mp_authority, Mapping)
        or not isinstance(runtime_contract, Mapping)
    ):
        raise BaselineDevelopmentPublicationGuardPatchError("Cannot construct E0-MQ companion inputs")
    h_components = _validate_h_component_records(h_patch)
    preserved = mp_authority.get("preserved_records")
    historical = mp_authority.get("historical_records")
    physical_inputs = runtime_contract.get("physical_inputs")
    if (
        not isinstance(physical_inputs, list)
        or not isinstance(preserved, list)
        or not isinstance(historical, list)
    ):
        raise BaselineDevelopmentPublicationGuardPatchError("Cannot construct E0-MQ physical inputs")
    inputs = [
        dict(record)
        for record in (*physical_inputs, *preserved, *h_components)
    ]
    inputs.sort(key=lambda record: str(record.get("path")))
    input_paths = [str(record.get("path")) for record in inputs]
    if (
        len(inputs) != EXPECTED_COMPANION_INPUT_COUNT
        or len(set(input_paths)) != EXPECTED_COMPANION_INPUT_COUNT
    ):
        raise BaselineDevelopmentPublicationGuardPatchError(
            "E0-MQ companion must bind exactly 53 unique physical inputs"
        )
    if (
        len(historical) != EXPECTED_HISTORICAL_INPUT_COUNT
        or len({str(record.get("path")) for record in historical})
        != EXPECTED_HISTORICAL_INPUT_COUNT
        or any(record.get("commit") != H_MP_COMMIT for record in historical)
        or any(record.get("hash_source") != "git_blob_at_commit" for record in historical)
    ):
        raise BaselineDevelopmentPublicationGuardPatchError(
            "E0-MQ companion historical inputs drifted"
        )
    script = next(
        dict(record)
        for record in h_components
        if record["path"]
        == "src/experiments/lock_closure_baseline_development_publication_guard_patch.py"
    )
    return {
        "manifest_version": "closure_baseline_development_publication_guard_patch_lock_manifest_v1",
        "gate": PATCH_GATE,
        "status": "completed",
        "inputs": inputs,
        "historical_inputs": [dict(record) for record in historical],
        "script": script,
        "outputs": [dict(lock_record)],
        "manifest_written_last": True,
        "physical_inputs_only": True,
        "historical_inputs_compared_to_current_paths": False,
        "dvc_commands_run": False,
        "network_commands_run": True,
        "data_execution_run": False,
        "future_outcomes_accessed": False,
    }


def load_and_validate_baseline_development_publication_guard_patch_lock(
    lock_path: Path = DEFAULT_PATCH_LOCK_PATH,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    payload = _load_regular_json(lock_path, context="E0-MQ lock", repo_root=repo_root)
    return validate_baseline_development_publication_guard_patch_lock_payload(payload, repo_root=repo_root)


def _validate_p_publication(
    payload: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, str]:
    root = _root(repo_root)
    head = _git("rev-parse", "HEAD", repo_root=root)
    parent = _single_parent(head, repo_root=root)
    tracking = _git("rev-parse", PUBLISHED_REF, repo_root=root)
    remote = _live_remote_main_head(repo_root=root)
    if (
        parent != payload["repository"]["head"]
        or tracking != head
        or remote != head
    ):
        raise BaselineDevelopmentPublicationGuardPatchError("Published P topology/ref alignment drifted")
    if _git("branch", "--show-current", repo_root=root) != "main":
        raise BaselineDevelopmentPublicationGuardPatchError("Published P branch drifted")
    if _git("status", "--porcelain=v1", "--untracked-files=all", repo_root=root):
        raise BaselineDevelopmentPublicationGuardPatchError("Published P repository must be clean")
    entries = _observed_diff_entries(parent, head, repo_root=root)
    expected = [
        {"status": "A", "path": DEFAULT_PATCH_LOCK_PATH.as_posix()},
        {"status": "A", "path": DEFAULT_PATCH_MANIFEST_PATH.as_posix()},
    ]
    if sorted(entries, key=lambda item: item["path"]) != expected:
        raise BaselineDevelopmentPublicationGuardPatchError("P-E0-MQ is not exactly lock+companion")
    lock_record = _file_record(DEFAULT_PATCH_LOCK_PATH, role="baseline_development_publication_guard_patch_lock", repo_root=root)
    companion = _load_regular_json(
        DEFAULT_PATCH_MANIFEST_PATH,
        context="E0-MQ companion",
        repo_root=root,
    )
    if companion != _expected_companion(payload, lock_record):
        raise BaselineDevelopmentPublicationGuardPatchError("Published E0-MQ companion drifted")
    _reconstruct_h_components(payload, repo_root=root)
    if payload.get("mp_authority") != _historical_mp_authority(repo_root=root):
        raise BaselineDevelopmentPublicationGuardPatchError(
            "Published E0-MQ historical H-E0-MP authority drifted"
        )
    runtime = load_and_validate_baseline_development_runtime(
        repo_root=root,
        verify_physical_pins=False,
    )
    observed_physical_inputs = _verify_runtime_physical_pins(runtime, repo_root=root)
    runtime_contract = payload.get("runtime_contract")
    if (
        not isinstance(runtime_contract, Mapping)
        or runtime_contract.get("physical_inputs") != observed_physical_inputs
        or runtime_contract.get("physical_inputs_sha256")
        != _record_digest(observed_physical_inputs)
    ):
        raise BaselineDevelopmentPublicationGuardPatchError("Published E0-MQ physical inputs drifted")
    baseline_output_namespace_absence(runtime, repo_root=root)
    for path in (
        MP_FAILED_LOCK_PATH,
        MP_FAILED_MANIFEST_PATH,
        *MP_FAILED_TEMP_PATHS,
        MP_FAILED_GUARD_PATH,
        *CURRENT_TEMP_PATHS,
        CURRENT_GUARD_PATH,
    ):
        if _lexists(root / path):
            raise BaselineDevelopmentPublicationGuardPatchError(
                f"Published E0-MQ forbidden residual exists: {path}"
            )
    return {"h_patch_head": parent, "p_patch_head": head, "remote_head": remote}


def load_effective_baseline_development_publication_guard_authority(
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Return the only effective E0-MQ flags after exact P publication."""
    preflight_baseline_development_publication_guard_patch_schema(repo_root=repo_root)
    payload = load_and_validate_baseline_development_publication_guard_patch_lock(repo_root=repo_root)
    publication = _validate_p_publication(payload, repo_root=repo_root)
    h_patch = payload["h_patch"]
    runtime_contract = payload["runtime_contract"]
    lock_record = _file_record(
        DEFAULT_PATCH_LOCK_PATH,
        role="baseline_development_publication_guard_patch_lock",
        repo_root=repo_root,
    )
    companion_record = _file_record(
        DEFAULT_PATCH_MANIFEST_PATH,
        role="baseline_development_publication_guard_patch_lock_manifest",
        repo_root=repo_root,
    )
    return {
        "gate": PATCH_GATE,
        "status": "effective_preflight_passed",
        **EFFECTIVE_AUTHORIZATIONS,
        "development_target_access_end": "2020-12",
        "target_projection": list(TARGET_PROJECTION),
        "h_patch_head": publication["h_patch_head"],
        "p_patch_head": publication["p_patch_head"],
        "lock_sha256": lock_record["sha256"],
        "companion_sha256": companion_record["sha256"],
        "runtime_sha256": runtime_contract["record"]["sha256"],
        "h_components_sha256": h_patch["components_sha256"],
        "physical_inputs_sha256": runtime_contract["physical_inputs_sha256"],
        "runner_sha256": next(
            record["sha256"]
            for record in h_patch["components"]
            if record["path"] == "src/experiments/fit_closure_baselines.py"
        ),
    }


def require_baseline_development_publication_guard_authority(
    *,
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Compatibility hook used as the runner's first post-parse operation.

    ``verify_remote`` is mandatory: the gate performs a read-only
    ``git ls-remote`` alignment check.  Scientific execution remains
    network-closed.
    """
    if verify_remote is not True:
        raise BaselineDevelopmentPublicationGuardPatchError("E0-MQ requires tracking-ref verification")
    return load_effective_baseline_development_publication_guard_authority(
        repo_root=repo_root
    )
