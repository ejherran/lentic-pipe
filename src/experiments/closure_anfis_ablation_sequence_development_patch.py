#!/usr/bin/env python
"""Validate the input-only Closure V1 A0/A1 sequence authority.

E0-MS may bind and later authorize six development-only input bundles: one
shared A0 raw bundle and five A1 bundles paired to the five frozen ANFIS
states.  H/P may hash physical inputs and perform a read-only Git remote
alignment check.  It cannot build a sequence, open targets/outcomes, fit a
model, calibrate, score metrics, run DVC, or create E0-M/E0-U artifacts.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import yaml
from yaml.constructor import ConstructorError
from yaml.resolver import BaseResolver

from src.experiments import closure_contract
from src.experiments.closure_contract import ClosureContractError, validate_json_schema


PROJECT_ROOT = Path(__file__).resolve().parents[2]

LOCK_VERSION = "closure_anfis_ablation_sequence_development_patch_lock_v1"
PATCH_GATE = "E0-MS"
PATCH_ID = "anfis_ablation_sequence_development_authority_patch_1"
EXPERIMENT_ID = "closure_v1"
SURFACE_ID = "closure_v1_wqp_adaptive_no_current_chla"
PATCH_BASE_COMMIT = "0a323b0b4c73384558b7782f63512b342a5411c5"
PATCH_BASE_PARENT = "9106ff042ecea135d3652e8dedac4d78a2360b3e"
PUBLISHED_REF = "origin/main"

DEFAULT_RUNTIME_PATH = Path(
    "configs/closure_v1/anfis_ablation_sequence_development_runtime.yaml"
)
DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/anfis_ablation_sequence_development_patch_lock.schema.json"
)
DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "anfis_ablation_sequence_development_patch_lock.json"
)
DEFAULT_PATCH_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "anfis_ablation_sequence_development_patch_lock_manifest.json"
)
LOCKER_GUARD_PATH = Path(
    "tmp/closure_v1_anfis_ablation_sequence_development_patch/lock_bundle.guard"
)

PATCH_COMPONENT_ROLES = {
    DEFAULT_PATCH_LOCK_SCHEMA.as_posix(): (
        "anfis_ablation_sequence_development_patch_lock_schema"
    ),
    DEFAULT_RUNTIME_PATH.as_posix(): "anfis_ablation_sequence_development_runtime",
    "docs/closure_v1/E0_M_ANFIS_ABLATION_SEQUENCE_DEVELOPMENT_PATCH_1.md": (
        "anfis_ablation_sequence_development_patch_protocol"
    ),
    "src/experiments/audit_closure_anfis_ablation_sequence_bundle.py": (
        "anfis_ablation_sequence_bundle_auditor"
    ),
    "src/experiments/build_closure_anfis_ablation_sequences.py": (
        "anfis_ablation_sequence_builder"
    ),
    "src/experiments/closure_anfis_ablation_sequence_development_patch.py": (
        "anfis_ablation_sequence_development_patch_validator"
    ),
    "src/experiments/lock_closure_anfis_ablation_sequence_development_patch.py": (
        "anfis_ablation_sequence_development_patch_locker"
    ),
    "tests/test_audit_closure_anfis_ablation_sequence_bundle.py": (
        "anfis_ablation_sequence_bundle_auditor_tests"
    ),
    "tests/test_build_closure_anfis_ablation_sequences.py": (
        "anfis_ablation_sequence_builder_tests"
    ),
    "tests/test_closure_anfis_ablation_sequence_development_patch.py": (
        "anfis_ablation_sequence_development_patch_tests"
    ),
}
PATCH_PATHS = tuple(sorted(PATCH_COMPONENT_ROLES))

PHYSICAL_INPUT_ROLES = {
    "reports/closure_v1/00_protocol/protocol_lock.json": "protocol_lock",
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
    "reports/closure_v1/00_protocol/"
    "baseline_development_publication_guard_patch_lock.json": "baseline_patch_lock",
    "reports/closure_v1/00_protocol/"
    "baseline_development_publication_guard_patch_lock_manifest.json": (
        "baseline_patch_lock_manifest"
    ),
    "reports/closure_v1/02_models/baselines/manifest.json": (
        "baseline_bundle_manifest"
    ),
    "data/closure_v1/development/baselines/B0/raw_scores.parquet.dvc": (
        "baseline_b0_pointer"
    ),
    "data/closure_v1/development/baselines/B1/raw_scores.parquet.dvc": (
        "baseline_b1_pointer"
    ),
    "data/closure_v1/development/baselines/B2/raw_scores.parquet.dvc": (
        "baseline_b2_pointer"
    ),
    "reports/closure_v1/00_protocol/mifal_development_patch_lock.json": (
        "m0_patch_lock"
    ),
    "reports/closure_v1/00_protocol/mifal_development_patch_lock_manifest.json": (
        "m0_patch_lock_manifest"
    ),
    "data/closure_v1/development/mifal/M0/raw_scores.parquet.dvc": "m0_raw_pointer",
    "reports/closure_v1/02_models/M0/model_spec.json": "m0_model_spec",
    "reports/closure_v1/02_models/M0/lineage_audit.json": "m0_lineage_audit",
    "reports/closure_v1/02_models/M0/availability.csv": "m0_availability",
    "reports/closure_v1/02_models/M0/report.md": "m0_report",
    "reports/closure_v1/02_models/M0/manifest.json": "m0_manifest",
    "data/closure_v1/development/anfis/seed_1729/"
    "adaptive_no_current_state.parquet": "anfis_state_seed_1729",
    "data/closure_v1/development/anfis/seed_1729/"
    "adaptive_no_current_state.parquet.dvc": "anfis_state_pointer_seed_1729",
    "reports/closure_v1/01_surface/anfis/seed_1729/manifest.json": (
        "anfis_manifest_seed_1729"
    ),
    "data/closure_v1/development/anfis/seed_20260612/"
    "adaptive_no_current_state.parquet": "anfis_state_seed_20260612",
    "data/closure_v1/development/anfis/seed_20260612/"
    "adaptive_no_current_state.parquet.dvc": (
        "anfis_state_pointer_seed_20260612"
    ),
    "reports/closure_v1/01_surface/anfis/seed_20260612/manifest.json": (
        "anfis_manifest_seed_20260612"
    ),
    "data/closure_v1/development/anfis/seed_20260613/"
    "adaptive_no_current_state.parquet": "anfis_state_seed_20260613",
    "data/closure_v1/development/anfis/seed_20260613/"
    "adaptive_no_current_state.parquet.dvc": (
        "anfis_state_pointer_seed_20260613"
    ),
    "reports/closure_v1/01_surface/anfis/seed_20260613/manifest.json": (
        "anfis_manifest_seed_20260613"
    ),
    "data/closure_v1/development/anfis/seed_20260614/"
    "adaptive_no_current_state.parquet": "anfis_state_seed_20260614",
    "data/closure_v1/development/anfis/seed_20260614/"
    "adaptive_no_current_state.parquet.dvc": (
        "anfis_state_pointer_seed_20260614"
    ),
    "reports/closure_v1/01_surface/anfis/seed_20260614/manifest.json": (
        "anfis_manifest_seed_20260614"
    ),
    "data/closure_v1/development/anfis/seed_314159/"
    "adaptive_no_current_state.parquet": "anfis_state_seed_314159",
    "data/closure_v1/development/anfis/seed_314159/"
    "adaptive_no_current_state.parquet.dvc": "anfis_state_pointer_seed_314159",
    "reports/closure_v1/01_surface/anfis/seed_314159/manifest.json": (
        "anfis_manifest_seed_314159"
    ),
    "pyproject.toml": "pyproject",
    "poetry.lock": "poetry_lock",
    "models.dvc": "models_dvc_observer",
}
PHYSICAL_INPUT_PATHS = tuple(PHYSICAL_INPUT_ROLES)
EXPECTED_RUNTIME_PHYSICAL_INPUT_COUNT = 44
EXPECTED_COMPANION_INPUT_COUNT = 54

REGISTERED_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
ORDERED_BUNDLE_SLOTS: tuple[tuple[str, int | None], ...] = (
    ("A0", None),
    *(("A1", seed) for seed in REGISTERED_SEEDS),
)
RAW_MEAN_COLUMNS = (
    "mean_TP_ugL",
    "mean_TN_ugL",
    "mean_DO_mgL",
    "mean_pH",
    "mean_turbidity_NTU",
    "mean_secchi_depth_m",
    "mean_temperature_C",
)
RAW_N_OBS_COLUMNS = tuple(column.replace("mean_", "n_obs_", 1) for column in RAW_MEAN_COLUMNS)
RAW_VALUE_COLUMNS = tuple(f"x_{column}" for column in RAW_MEAN_COLUMNS)
RAW_MASK_COLUMNS = tuple(f"mask_{column}" for column in RAW_MEAN_COLUMNS)
SEASON_COLUMNS = (
    "season_sin_annual",
    "season_cos_annual",
    "season_sin_semiannual",
    "season_cos_semiannual",
)
A0_INPUT_COLUMNS = RAW_VALUE_COLUMNS + RAW_MASK_COLUMNS + SEASON_COLUMNS
A1_STATE_COLUMNS = (
    "x_yN",
    "x_yF",
    "x_yT",
    "x_sigma_N",
    "x_sigma_F",
    "x_sigma_T",
    "x_delta_yN",
    "x_delta_yF",
    "x_delta_yT",
)
A1_STATE_SOURCE_MAPPING = {
    "x_yN": "yN_adaptive",
    "x_yF": "yF_adaptive",
    "x_yT": "yT_no_chla_adaptive",
    "x_sigma_N": "sigma_N_adaptive",
    "x_sigma_F": "sigma_F_adaptive",
    "x_sigma_T": "sigma_T_no_chla_adaptive",
    "x_delta_yN": "delta_yN_adaptive",
    "x_delta_yF": "delta_yF_adaptive",
    "x_delta_yT": "delta_yT_no_chla_adaptive",
}
A1_INPUT_COLUMNS = A0_INPUT_COLUMNS + A1_STATE_COLUMNS
IDENTITY_COLUMNS = (
    "sequence_version",
    "surface_id",
    "model_id",
    "base_seed",
    "upstream_state_seed",
    "source_id",
    "site_id",
    "common_origin_id",
    "holdout_group_id",
    "assignment_role",
    "time_role",
    "origin_year_month",
    "history_start_year_month",
    "history_end_year_month",
    "history_length_months",
    "sequence_status",
    "failure_reason",
)
ROW_STATUS_VALUES = ("success", "input_history_unavailable", "model_slot_unavailable")

A0_FINAL_PATHS = (
    "data/closure_v1/development/sequences/A0/raw_no_current.parquet",
    "reports/closure_v1/01_surface/sequences/A0/raw_no_current_summary.csv",
    "reports/closure_v1/01_surface/sequences/A0/raw_no_current_manifest.json",
)
A1_FINAL_PATHS = tuple(
    path
    for seed in REGISTERED_SEEDS
    for path in (
        f"data/closure_v1/development/sequences/A1/seed_{seed}.parquet",
        f"reports/closure_v1/01_surface/sequences/A1/seed_{seed}_summary.csv",
        f"reports/closure_v1/01_surface/sequences/A1/seed_{seed}_manifest.json",
    )
)
ABLATION_SEQUENCE_FINAL_PATHS = A0_FINAL_PATHS + A1_FINAL_PATHS
ABLATION_SEQUENCE_POINTER_PATHS = (
    "data/closure_v1/development/sequences/A0/raw_no_current.parquet.dvc",
    *(
        f"data/closure_v1/development/sequences/A1/seed_{seed}.parquet.dvc"
        for seed in REGISTERED_SEEDS
    ),
)
ABLATION_SEQUENCE_GUARD_PATHS = (
    "tmp/closure_v1_anfis_ablation_sequences/A0_raw_no_current.guard",
    *(
        f"tmp/closure_v1_anfis_ablation_sequences/A1_seed_{seed}.guard"
        for seed in REGISTERED_SEEDS
    ),
)

E0_M_PATHS = (
    "reports/closure_v1/00_protocol/model_lock.yaml",
    "reports/closure_v1/00_protocol/calibration_lock.yaml",
    "reports/closure_v1/00_protocol/hypothesis_registry.csv",
    "reports/closure_v1/00_protocol/locked_batch_command.txt",
)
OUTCOME_ACCESS_LOG = "reports/closure_v1/00_protocol/outcome_access_log.jsonl"

TYPE_CHECK_COMMAND = (".venv/bin/ty", "check")
FOCUSED_TEST_COMMAND = (
    ".venv/bin/python",
    "-m",
    "pytest",
    "-q",
    "tests/test_closure_anfis_ablation_sequence_development_patch.py",
    "tests/test_build_closure_anfis_ablation_sequences.py",
    "tests/test_audit_closure_anfis_ablation_sequence_bundle.py",
)
# Frozen after exact collection of all three focused files.
FOCUSED_TEST_COUNT = 63
POETRY_CHECK_COMMAND = ("poetry", "check")
PUBLICATION_GUARD_COMMAND = ("scripts/check_repo_publication_ready.sh",)
DIFF_CHECK_COMMAND = ("git", "diff", "--check")

UNPUBLISHED_AUTHORIZATIONS = {
    "a0_sequence_build_authorized": False,
    "a1_sequence_build_authorized": False,
    "sequence_bundle_audit_authorized": False,
    "temporal_fit_authorized": False,
    "target_access_authorized": False,
    "calibration_authorized": False,
    "metrics_authorized": False,
    "rollout_authorized": False,
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
    "a0_sequence_build_authorized": True,
    "a1_sequence_build_authorized": True,
    "sequence_bundle_audit_authorized": False,
    "temporal_fit_authorized": False,
    "target_access_authorized": False,
    "calibration_authorized": False,
    "metrics_authorized": False,
    "rollout_authorized": False,
    "e0_m_authorized": False,
    "evaluation_authorized": False,
    "e0_u_authorized": False,
    "dvc_commands_authorized": False,
    "scientific_network_authorized": False,
    "outcome_access_authorized": False,
    "future_outcomes_accessed": False,
}
PATCH_SEALS = {
    "input_only": True,
    "exact_a0_input_dimension": 18,
    "exact_a1_input_dimension": 27,
    "exact_bundle_count": 6,
    "targets_absent": True,
    "fit_absent": True,
    "calibration_absent": True,
    "metrics_absent": True,
    "rollout_absent": True,
    "e7_learning_curve_sizes_authorized": False,
    "e7_learning_curve_status": "blocked_for_separate_gate",
    "no_best_seed_selection": True,
    "no_seed_pooling_as_independent_observations": True,
    "no_chlorophyll_predictor_or_lineage": True,
    "no_holdout_or_post_2021_outcomes": True,
    "current_p0_p1_status": "model_unavailable_not_attempted",
    "replacement_or_substitution_authorized": False,
    "e7_comparison_status": (
        "non_estimable_until_comparator_and_ablation_models_available"
    ),
    "e7_claims_authorized": False,
}


class AnfisAblationSequenceDevelopmentPatchError(RuntimeError):
    """Raised when E0-MS cannot prove its exact closed authority."""


def _root(repo_root: Path | None = None) -> Path:
    return (repo_root or PROJECT_ROOT).resolve()


def _relative(path: Path, *, repo_root: Path | None = None) -> str:
    root = _root(repo_root)
    candidate = path if path.is_absolute() else root / path
    try:
        return candidate.relative_to(root).as_posix()
    except ValueError as exc:
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"Path escapes repository: {path}"
        ) from exc


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ": "),
        ).encode("utf-8")
        + b"\n"
    )


def _path_digest(paths: Sequence[str]) -> str:
    return _sha256_bytes("\n".join(paths).encode("utf-8"))


def _record_digest(records: Sequence[Mapping[str, Any]]) -> str:
    normalized = [dict(record) for record in records]
    return _sha256_bytes(
        json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _repo_relative_parts(path: Path, *, repo_root: Path | None = None) -> tuple[str, ...]:
    root = _root(repo_root)
    candidate = path if path.is_absolute() else root / path
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"Path escapes repository: {path}"
        ) from exc
    parts = relative.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"Invalid repository path: {path}"
        )
    return parts


def _read_regular_bytes(path: Path, *, repo_root: Path | None = None) -> bytes:
    """Read through anchored dirfds; reject symlink ancestors and mutation."""
    root = _root(repo_root)
    parts = _repo_relative_parts(path, repo_root=root)
    directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    descriptor = -1
    try:
        for component in parts[:-1]:
            next_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=directory_fd,
            )
            os.close(directory_fd)
            directory_fd = next_fd
        descriptor = os.open(
            parts[-1],
            os.O_RDONLY | os.O_NOFOLLOW,
            dir_fd=directory_fd,
        )
        before = os.fstat(descriptor)
        named_before = os.stat(parts[-1], dir_fd=directory_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode)
            or not stat.S_ISREG(named_before.st_mode)
            or (named_before.st_dev, named_before.st_ino)
            != (before.st_dev, before.st_ino)
        ):
            raise AnfisAblationSequenceDevelopmentPatchError(
                f"Required path is not regular: {path.as_posix()}"
            )
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        payload = b"".join(chunks)
        after = os.fstat(descriptor)
        named_after = os.stat(parts[-1], dir_fd=directory_fd, follow_symlinks=False)
        identity_before = (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_size,
            before.st_mtime_ns,
        )
        identity_after = (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_size,
            after.st_mtime_ns,
        )
        named_identity_before = (
            named_before.st_dev,
            named_before.st_ino,
            named_before.st_mode,
            named_before.st_size,
            named_before.st_mtime_ns,
            named_before.st_ctime_ns,
        )
        named_identity_after = (
            named_after.st_dev,
            named_after.st_ino,
            named_after.st_mode,
            named_after.st_size,
            named_after.st_mtime_ns,
            named_after.st_ctime_ns,
        )
        if (
            identity_after != identity_before
            or named_identity_after != named_identity_before
            or (named_after.st_dev, named_after.st_ino) != (after.st_dev, after.st_ino)
            or len(payload) != before.st_size
        ):
            raise AnfisAblationSequenceDevelopmentPatchError(
                f"Required file changed during anchored read: {path.as_posix()}"
            )
        return payload
    except (FileNotFoundError, NotADirectoryError, OSError) as exc:
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"Required regular file is unavailable or symlinked: {path.as_posix()}"
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(directory_fd)


def _file_record(
    path: Path,
    *,
    role: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    payload = _read_regular_bytes(path, repo_root=repo_root)
    return {
        "path": path.as_posix(),
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
    def reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        payload = json.loads(
            _read_regular_bytes(path, repo_root=repo_root),
            object_pairs_hook=reject_duplicate_pairs,
        )
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"{context} is not valid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"{context} must contain a JSON object"
        )
    return payload


class _UniqueSafeLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: _UniqueSafeLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueSafeLoader.add_constructor(
    BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _keyword_occurrences(value: Any, keyword: str) -> int:
    if isinstance(value, Mapping):
        return sum(
            int(key == keyword) + _keyword_occurrences(child, keyword)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return sum(_keyword_occurrences(child, keyword) for child in value)
    return 0


def _require_equal(observed: Any, expected: Any, context: str) -> None:
    if observed != expected:
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"E0-MS {context} drifted"
        )


def preflight_anfis_ablation_sequence_development_patch_schema(
    schema_path: Path = DEFAULT_PATCH_LOCK_SCHEMA,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Validate the physical lock schema before guards or other commands."""
    if schema_path != DEFAULT_PATCH_LOCK_SCHEMA:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS requires the closed default schema path"
        )
    schema = _load_regular_json(
        schema_path,
        context="E0-MS lock schema",
        repo_root=repo_root,
    )
    minimum_count = _keyword_occurrences(schema, "minimum")
    format_count = _keyword_occurrences(schema, "format")
    if minimum_count or format_count:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS schema uses unsupported keywords: "
            f"minimum={minimum_count}, format={format_count}"
        )
    validator = getattr(closure_contract, "_assert_supported_json_schema", None)
    if not callable(validator):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "Closure JSON-schema definition validator is unavailable"
        )
    try:
        validator(schema)
    except ClosureContractError as exc:
        raise AnfisAblationSequenceDevelopmentPatchError(str(exc)) from exc
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


def _validate_record_shape(record: Any, *, expected_path: str, expected_role: str) -> None:
    if not isinstance(record, Mapping) or set(record) != {
        "path",
        "role",
        "bytes",
        "sha256",
    }:
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"E0-MS physical record dialect drifted for {expected_path}"
        )
    digest = record.get("sha256")
    if (
        record.get("path") != expected_path
        or record.get("role") != expected_role
        or not isinstance(record.get("bytes"), int)
        or int(record["bytes"]) < 1
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"E0-MS physical record drifted for {expected_path}"
        )


def _verify_runtime_physical_pins(
    runtime: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> list[dict[str, Any]]:
    authority = runtime.get("authority")
    if not isinstance(authority, Mapping):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS runtime authority is absent"
        )
    raw_records = authority.get("physical_inputs")
    if (
        authority.get("physical_input_count") != EXPECTED_RUNTIME_PHYSICAL_INPUT_COUNT
        or not isinstance(raw_records, list)
        or len(raw_records) != EXPECTED_RUNTIME_PHYSICAL_INPUT_COUNT
    ):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS physical input count drifted"
        )
    paths = [record.get("path") if isinstance(record, Mapping) else None for record in raw_records]
    if tuple(paths) != PHYSICAL_INPUT_PATHS or len(set(paths)) != len(paths):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS physical input order/uniqueness drifted"
        )
    observed: list[dict[str, Any]] = []
    for record, path in zip(raw_records, PHYSICAL_INPUT_PATHS, strict=True):
        role = PHYSICAL_INPUT_ROLES[path]
        _validate_record_shape(record, expected_path=path, expected_role=role)
        if not isinstance(record, Mapping):
            raise AnfisAblationSequenceDevelopmentPatchError(
                f"E0-MS physical record is not a mapping: {path}"
            )
        actual = _file_record(Path(path), role=role, repo_root=repo_root)
        normalized_record = dict(cast(Mapping[str, Any], record))
        if normalized_record != actual:
            raise AnfisAblationSequenceDevelopmentPatchError(
                f"E0-MS physical pin drifted: {path}"
            )
        observed.append(actual)
    return observed


def _validate_progression_manifests(*, repo_root: Path | None = None) -> None:
    baseline = _load_regular_json(
        Path("reports/closure_v1/02_models/baselines/manifest.json"),
        context="Closure baseline manifest",
        repo_root=repo_root,
    )
    if (
        baseline.get("experiment_id") != EXPERIMENT_ID
        or baseline.get("status") != "completed"
        or baseline.get("gate") != "E0-MQ"
        or baseline.get("future_outcomes_accessed") is not False
        or baseline.get("dvc_commands_run") is not False
        or next(reversed(baseline), None) != "completion_marker_written_last"
        or baseline.get("completion_marker_written_last") is not True
    ):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS baseline progression manifest drifted"
        )
    m0 = _load_regular_json(
        Path("reports/closure_v1/02_models/M0/manifest.json"),
        context="Closure M0 manifest",
        repo_root=repo_root,
    )
    if (
        m0.get("experiment_id") != EXPERIMENT_ID
        or m0.get("model_id") != "M0"
        or m0.get("status") != "mifal_development_bundle_written_unpublished"
        or m0.get("gate") != "E0-MR"
        or m0.get("targets_opened") is not False
        or m0.get("calibration_performed") is not False
        or m0.get("metrics_computed") is not False
        or m0.get("dvc_commands_run") is not False
        or m0.get("future_outcomes_accessed") is not False
        or next(reversed(m0), None) != "completion_marker_written_last"
        or m0.get("completion_marker_written_last") is not True
    ):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS M0 progression manifest drifted"
        )


def _validate_runtime_science(runtime: Mapping[str, Any]) -> None:
    roles = runtime.get("roles")
    if not isinstance(roles, Mapping):
        raise AnfisAblationSequenceDevelopmentPatchError("E0-MS roles are absent")
    _require_equal(
        dict(roles),
        {
            "training_end": "2018-12",
            "model_selection_start": "2019-01",
            "model_selection_end": "2020-12",
            "calibration_threshold_start": "2021-01",
            "calibration_threshold_end": "2021-12",
            "locked_evaluation_start": "2022-01",
            "origin_and_target_must_share_role": True,
            "holdout_locations_excluded": True,
            "target_artifacts_opened": False,
        },
        "role contract",
    )
    denominators = runtime.get("denominators")
    if not isinstance(denominators, Mapping):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS denominators are absent"
        )
    _require_equal(denominators.get("common_origin_rows"), 29196, "common rows")
    _require_equal(denominators.get("intent_origins"), 9732, "intent origins")
    _require_equal(
        denominators.get("development_locations"), 353, "development locations"
    )
    _require_equal(denominators.get("history_length_months"), 12, "history")
    _require_equal(denominators.get("horizons_months"), [1, 2, 3], "horizons")
    _require_equal(
        denominators.get("intent_origins_by_role"),
        {"training": 8352, "model_selection": 1061, "calibration_threshold": 319},
        "role denominators",
    )
    _require_equal(
        denominators.get("retention_policy"),
        "retain_all_intent_origins_with_status_and_reason",
        "retention policy",
    )

    features = runtime.get("features")
    if not isinstance(features, Mapping):
        raise AnfisAblationSequenceDevelopmentPatchError("E0-MS features are absent")
    common = features.get("common")
    raw = features.get("raw_no_current")
    state = features.get("adaptive_state")
    models = features.get("models")
    if not all(isinstance(item, Mapping) for item in (common, raw, state, models)):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS feature sections are incomplete"
        )
    _require_equal(common.get("history_length_months"), 12, "feature history")
    _require_equal(common.get("target_columns"), [], "target columns")
    _require_equal(common.get("target_scan_authorized"), False, "target scan")
    _require_equal(common.get("serialization_dtype"), "float32", "dtype")
    _require_equal(
        common.get("terminal_failure_tensor_policy"),
        "every_channel_parent_list_is_null_and_no_synthetic_vector_is_written",
        "terminal failure tensor",
    )
    _require_equal(raw.get("mean_columns"), list(RAW_MEAN_COLUMNS), "E6 means")
    _require_equal(raw.get("n_obs_columns"), list(RAW_N_OBS_COLUMNS), "E6 counts")
    _require_equal(
        raw.get("serialized_value_columns"), list(RAW_VALUE_COLUMNS), "raw channels"
    )
    _require_equal(
        raw.get("observed_mask_columns"), list(RAW_MASK_COLUMNS), "mask channels"
    )
    _require_equal(raw.get("exact_input_order"), list(A0_INPUT_COLUMNS), "A0 order")
    _require_equal(raw.get("exact_input_dimension"), 18, "A0 dimension")
    _require_equal(raw.get("logical_tensor_shape"), [12, 18], "A0 shape")
    _require_equal(
        raw.get("missing_mean_serialization"),
        "structural_zero_float32_with_corresponding_mask_zero",
        "raw missing transport",
    )
    _require_equal(
        raw.get("structural_zero_is_scientific_imputation"),
        False,
        "raw fill semantics",
    )
    _require_equal(
        state.get("exact_state_order"), list(A1_STATE_COLUMNS), "A1 state order"
    )
    _require_equal(
        state.get("state_source_mapping"), A1_STATE_SOURCE_MAPPING, "A1 state mapping"
    )
    _require_equal(state.get("upstream_seed_policy"), "same_seed_slot", "A1 seed")
    _require_equal(models.get("A0", {}).get("exact_input_dimension"), 18, "A0 model")
    _require_equal(models.get("A1", {}).get("exact_input_dimension"), 27, "A1 model")
    _require_equal(models.get("A1", {}).get("logical_tensor_shape"), [12, 27], "A1 shape")

    bundles = runtime.get("bundles")
    if not isinstance(bundles, Mapping):
        raise AnfisAblationSequenceDevelopmentPatchError("E0-MS bundles are absent")
    _require_equal(bundles.get("ordered_base_seeds"), list(REGISTERED_SEEDS), "seeds")
    _require_equal(bundles.get("exact_bundle_count"), 6, "bundle count")
    _require_equal(
        bundles.get("ordered_bundle_slots"),
        [
            {"model_id": model_id, "base_seed": base_seed}
            for model_id, base_seed in ORDERED_BUNDLE_SLOTS
        ],
        "ordered bundle slots",
    )
    _require_equal(
        bundles.get("progression_policy"),
        "exact_completed_untracked_prefix_no_pointers_until_all_six",
        "bundle progression",
    )
    _require_equal(bundles.get("identity_columns"), list(IDENTITY_COLUMNS), "identity")
    _require_equal(bundles.get("row_status_values"), list(ROW_STATUS_VALUES), "statuses")
    _require_equal(
        bundles.get("training_or_model_fit"), "forbidden", "fit prohibition"
    )
    parquet = bundles.get("parquet_contract")
    if not isinstance(parquet, Mapping):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS Parquet contract is absent"
        )
    expected_identity_schema = [
        {"name": "sequence_version", "arrow_type": "string", "nullable": False},
        {"name": "surface_id", "arrow_type": "string", "nullable": False},
        {"name": "model_id", "arrow_type": "string", "nullable": False},
        {"name": "base_seed", "arrow_type": "int64", "nullable": True},
        {"name": "upstream_state_seed", "arrow_type": "int64", "nullable": True},
        {"name": "source_id", "arrow_type": "string", "nullable": False},
        {"name": "site_id", "arrow_type": "string", "nullable": False},
        {"name": "common_origin_id", "arrow_type": "string", "nullable": False},
        {"name": "holdout_group_id", "arrow_type": "string", "nullable": False},
        {"name": "assignment_role", "arrow_type": "string", "nullable": False},
        {"name": "time_role", "arrow_type": "string", "nullable": False},
        {"name": "origin_year_month", "arrow_type": "string", "nullable": False},
        {"name": "history_start_year_month", "arrow_type": "string", "nullable": False},
        {"name": "history_end_year_month", "arrow_type": "string", "nullable": False},
        {"name": "history_length_months", "arrow_type": "int16", "nullable": False},
        {"name": "sequence_status", "arrow_type": "string", "nullable": False},
        {"name": "failure_reason", "arrow_type": "string", "nullable": False},
    ]
    identity_names = [record["name"] for record in expected_identity_schema]
    if len(identity_names) != len(set(identity_names)) or identity_names != list(IDENTITY_COLUMNS):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "Internal E0-MS identity schema is inconsistent"
        )
    _require_equal(
        parquet.get("schema_version"),
        "closure_anfis_ablation_input_sequence_v1",
        "Parquet schema version",
    )
    _require_equal(parquet.get("row_unit"), "one_row_per_common_origin", "row unit")
    _require_equal(parquet.get("exact_rows_per_bundle"), 9732, "Parquet rows")
    _require_equal(
        parquet.get("identity_columns"), expected_identity_schema, "Parquet identity"
    )
    _require_equal(
        parquet.get("model_channel_order"),
        {"A0": list(A0_INPUT_COLUMNS), "A1": list(A1_INPUT_COLUMNS)},
        "Parquet channel order",
    )
    _require_equal(
        parquet.get("forbidden_row_columns"),
        ["evaluation_unit_id", "target_year_month", "horizon_months"],
        "forbidden row identity",
    )
    _require_equal(parquet.get("horizons_manifest_only"), [1, 2, 3], "manifest horizons")
    _require_equal(
        parquet.get("channel_arrow_type"),
        "fixed_size_list_float32_length_12",
        "channel Arrow type",
    )
    _require_equal(parquet.get("channel_parent_nullable"), True, "parent nullability")
    _require_equal(parquet.get("channel_child_nullable"), False, "child nullability")
    _require_equal(
        parquet.get("seed_policy"),
        {
            "A0": {"base_seed": None, "upstream_state_seed": None},
            "A1": {"base_seed": "registered_seed", "upstream_state_seed": "equal_base_seed"},
        },
        "Parquet seed policy",
    )
    _require_equal(
        parquet.get("canonical_sort"),
        [
            "source_id_utf8_ascending",
            "site_id_utf8_ascending",
            "origin_year_month_ascending",
            "common_origin_id_utf8_ascending",
        ],
        "Parquet canonical sort",
    )
    _require_equal(
        parquet.get("success_policy"),
        "every_channel_parent_nonnull_length_12_and_finite_with_binary_masks",
        "success tensor",
    )
    _require_equal(
        parquet.get("failure_policy"),
        "every_channel_parent_null_and_no_synthetic_vector",
        "failure tensor",
    )

    outputs = runtime.get("outputs")
    if not isinstance(outputs, Mapping):
        raise AnfisAblationSequenceDevelopmentPatchError("E0-MS outputs are absent")
    _require_equal(outputs.get("exact_final_path_count"), 18, "final count")
    _require_equal(outputs.get("exact_pointer_path_count"), 6, "pointer count")
    _require_equal(
        outputs.get("transaction"),
        {
            "exclusive_guard": True,
            "parent_walk": "dirfd_no_follow",
            "temporary_sibling": True,
            "final_publication": "hardlink_no_clobber",
            "rollback": "owned_inode_only",
            "manifest_written_last": True,
        },
        "output transaction",
    )
    _require_equal(
        outputs.get("dvc"),
        {
            "commands_authorized_by_e0_ms": False,
            "registration_policy": "explicit_pointer_per_sequence_after_read_only_audit",
            "push_requires_separate_informed_authorization": True,
        },
        "DVC contract",
    )


def load_and_validate_anfis_ablation_sequence_development_runtime(
    runtime_path: Path = DEFAULT_RUNTIME_PATH,
    *,
    repo_root: Path | None = None,
    verify_physical_pins: bool = True,
) -> dict[str, Any]:
    """Load the closed input-only runtime without reading any data columns."""
    if runtime_path != DEFAULT_RUNTIME_PATH:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS requires the closed default runtime path"
        )
    try:
        runtime = yaml.load(
            _read_regular_bytes(runtime_path, repo_root=repo_root),
            Loader=_UniqueSafeLoader,
        )
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS runtime is not valid YAML"
        ) from exc
    if not isinstance(runtime, dict):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS runtime must contain a mapping"
        )
    expected_top = {
        "schema_version",
        "experiment_id",
        "surface_id",
        "status",
        "gate",
        "patch_id",
        "patch_base_commit",
        "authority",
        "patch_scope",
        "roles",
        "denominators",
        "features",
        "bundles",
        "outputs",
        "verification",
        "authorizations",
        "seals",
    }
    if set(runtime) != expected_top:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS runtime top-level dialect drifted"
        )
    identity = {
        "schema_version": "closure_anfis_ablation_sequence_development_runtime_v1",
        "experiment_id": EXPERIMENT_ID,
        "surface_id": SURFACE_ID,
        "status": "ready_to_lock",
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "patch_base_commit": PATCH_BASE_COMMIT,
    }
    for key, expected in identity.items():
        _require_equal(runtime.get(key), expected, f"runtime {key}")
    authority = runtime.get("authority")
    if not isinstance(authority, Mapping):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS runtime authority is absent"
        )
    for key, expected in {
        "branch": "main",
        "tracking_ref": PUBLISHED_REF,
        "published_ref": "refs/heads/main",
        "clean_committed_head_required": True,
        "m0_bundle_commit": PATCH_BASE_COMMIT,
        "m0_bundle_parent": PATCH_BASE_PARENT,
        "baseline_bundle_commit": "aa0d2cbfac186464a8b6e17b87d71aeedaa92c95",
        "physical_input_count": EXPECTED_RUNTIME_PHYSICAL_INPUT_COUNT,
    }.items():
        _require_equal(authority.get(key), expected, f"authority {key}")
    records = authority.get("physical_inputs")
    if not isinstance(records, list) or len(records) != EXPECTED_RUNTIME_PHYSICAL_INPUT_COUNT:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS runtime physical records drifted"
        )
    for record, path in zip(records, PHYSICAL_INPUT_PATHS, strict=True):
        _validate_record_shape(
            record,
            expected_path=path,
            expected_role=PHYSICAL_INPUT_ROLES[path],
        )
    patch_scope = runtime.get("patch_scope")
    if not isinstance(patch_scope, Mapping):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS runtime patch scope is absent"
        )
    _require_equal(
        dict(patch_scope),
        {
            "exact_added_count": 10,
            "exact_modified_count": 0,
            "exact_deleted_count": 0,
            "paths": list(PATCH_PATHS),
        },
        "H scope",
    )
    _validate_runtime_science(runtime)
    _require_equal(runtime.get("authorizations"), UNPUBLISHED_AUTHORIZATIONS, "flags")
    _require_equal(runtime.get("seals"), PATCH_SEALS, "seals")
    verification = runtime.get("verification")
    if not isinstance(verification, Mapping):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS verification contract is absent"
        )
    _require_equal(verification.get("full_type_check"), list(TYPE_CHECK_COMMAND), "ty")
    _require_equal(
        verification.get("focused_tests"), list(FOCUSED_TEST_COMMAND), "focused command"
    )
    _require_equal(
        verification.get("focused_test_count"), FOCUSED_TEST_COUNT, "focused count"
    )
    _require_equal(verification.get("poetry_check"), list(POETRY_CHECK_COMMAND), "poetry")
    _require_equal(
        verification.get("publication_guard"), list(PUBLICATION_GUARD_COMMAND), "publication"
    )
    _require_equal(verification.get("diff_check"), list(DIFF_CHECK_COMMAND), "diff")
    if verify_physical_pins:
        _verify_runtime_physical_pins(runtime, repo_root=repo_root)
        _validate_progression_manifests(repo_root=repo_root)
    return runtime


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def ablation_sequence_final_paths(runtime: Mapping[str, Any]) -> tuple[str, ...]:
    outputs = runtime.get("outputs")
    if not isinstance(outputs, Mapping):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS output namespace is absent"
        )
    a0 = outputs.get("A0")
    a1 = outputs.get("A1")
    if not isinstance(a0, Mapping) or not isinstance(a1, Mapping):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS A0/A1 output namespaces are absent"
        )
    derived = (
        str(a0.get("sequence")),
        str(a0.get("summary")),
        str(a0.get("manifest")),
        *(
            str(a1.get(template_key)).format(base_seed=seed)
            for seed in REGISTERED_SEEDS
            for template_key in (
                "sequence_template",
                "summary_template",
                "manifest_template",
            )
        ),
    )
    if derived != ABLATION_SEQUENCE_FINAL_PATHS:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS final path templates drifted"
        )
    return tuple(derived)


def _ablation_sequence_pointer_paths(runtime: Mapping[str, Any]) -> tuple[str, ...]:
    outputs = runtime.get("outputs")
    if not isinstance(outputs, Mapping):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS pointer namespace is absent"
        )
    a0 = outputs.get("A0")
    a1 = outputs.get("A1")
    if not isinstance(a0, Mapping) or not isinstance(a1, Mapping):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS pointer templates are absent"
        )
    derived = (
        str(a0.get("pointer")),
        *(str(a1.get("pointer_template")).format(base_seed=seed) for seed in REGISTERED_SEEDS),
    )
    if derived != ABLATION_SEQUENCE_POINTER_PATHS:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS pointer templates drifted"
        )
    return tuple(derived)


def _ablation_sequence_guard_paths(runtime: Mapping[str, Any]) -> tuple[str, ...]:
    outputs = runtime.get("outputs")
    if not isinstance(outputs, Mapping):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS guard namespace is absent"
        )
    a0 = outputs.get("A0")
    a1 = outputs.get("A1")
    if not isinstance(a0, Mapping) or not isinstance(a1, Mapping):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS guard templates are absent"
        )
    derived = (
        str(a0.get("guard")),
        *(str(a1.get("guard_template")).format(base_seed=seed) for seed in REGISTERED_SEEDS),
    )
    if derived != ABLATION_SEQUENCE_GUARD_PATHS:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS guard templates drifted"
        )
    return tuple(derived)


def anfis_ablation_sequence_output_namespace_absence(
    runtime: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Prove all six future bundles, pointers, temporaries and guards absent."""
    root = _root(repo_root)
    finals = ablation_sequence_final_paths(runtime)
    temporaries = tuple(f"{path}.tmp" for path in finals)
    pointers = _ablation_sequence_pointer_paths(runtime)
    pointer_temporaries = tuple(f"{path}.tmp" for path in pointers)
    guards = _ablation_sequence_guard_paths(runtime)
    present_finals = [path for path in finals if _lexists(root / path)]
    present_temporaries = [path for path in temporaries if _lexists(root / path)]
    present_pointers = [path for path in pointers if _lexists(root / path)]
    present_pointer_temporaries = [
        path for path in pointer_temporaries if _lexists(root / path)
    ]
    present_guards = [path for path in guards if _lexists(root / path)]
    if any(
        (
            present_finals,
            present_temporaries,
            present_pointers,
            present_pointer_temporaries,
            present_guards,
        )
    ):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS future sequence namespace is not empty"
        )
    return {
        "final_path_count": len(finals),
        "final_paths": list(finals),
        "final_paths_sha256": _path_digest(finals),
        "present_final_count": 0,
        "absent_final_count": len(finals),
        "temporary_path_count": len(temporaries),
        "temporary_paths": list(temporaries),
        "temporary_paths_sha256": _path_digest(temporaries),
        "present_temporary_count": 0,
        "pointer_path_count": len(pointers),
        "pointer_paths": list(pointers),
        "pointer_paths_sha256": _path_digest(pointers),
        "present_pointer_count": 0,
        "pointer_temporary_path_count": len(pointer_temporaries),
        "pointer_temporary_paths": list(pointer_temporaries),
        "pointer_temporary_paths_sha256": _path_digest(pointer_temporaries),
        "present_pointer_temporary_count": 0,
        "guard_path_count": len(guards),
        "guard_paths": list(guards),
        "guard_paths_sha256": _path_digest(guards),
        "present_guard_count": 0,
    }


def _require_prelock_control_namespace_absent(
    *, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    lock_temp = Path(f"{DEFAULT_PATCH_LOCK_PATH.as_posix()}.tmp")
    manifest_temp = Path(f"{DEFAULT_PATCH_MANIFEST_PATH.as_posix()}.tmp")
    paths = (
        DEFAULT_PATCH_LOCK_PATH,
        DEFAULT_PATCH_MANIFEST_PATH,
        lock_temp,
        manifest_temp,
        LOCKER_GUARD_PATH,
    )
    if any(_lexists(root / path) for path in paths):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS lock/control namespace is not empty"
        )
    return {
        "p_lock_path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "p_lock_absent": True,
        "p_manifest_path": DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
        "p_manifest_absent": True,
        "p_lock_temporary_absent": True,
        "p_manifest_temporary_absent": True,
        "p_guard_path": LOCKER_GUARD_PATH.as_posix(),
        "p_guard_absent": True,
    }


def _git(*args: str, repo_root: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=_root(repo_root),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"Git command failed: git {' '.join(args)}: {detail}"
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
    rows = [line.split() for line in output.splitlines() if line.strip()]
    if len(rows) != 1 or len(rows[0]) != 2 or rows[0][1] != "refs/heads/main":
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS live origin/main observation is ambiguous"
        )
    head = rows[0][0]
    if len(head) != 40 or any(character not in "0123456789abcdef" for character in head):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS live origin/main returned an invalid commit"
        )
    return head


def _single_parent(commit: str, *, repo_root: Path | None = None) -> str:
    row = _git("rev-list", "--parents", "-n", "1", commit, repo_root=repo_root).split()
    if len(row) != 2 or row[0] != commit:
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"Commit must have exactly one parent: {commit}"
        )
    return row[1]


def _observed_diff_entries(
    parent: str,
    head: str,
    *,
    repo_root: Path | None = None,
) -> list[dict[str, str]]:
    output = _git(
        "diff-tree",
        "--no-commit-id",
        "--name-status",
        "-r",
        parent,
        head,
        repo_root=repo_root,
    )
    entries: list[dict[str, str]] = []
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) != 2 or fields[0] not in {"A", "M", "D"}:
            raise AnfisAblationSequenceDevelopmentPatchError(
                "E0-MS encountered an unsupported H/P diff entry"
            )
        entries.append({"status": fields[0], "path": fields[1]})
    return entries


def _require_git_mode_100644(
    commit: str,
    path: str,
    *,
    repo_root: Path | None = None,
) -> None:
    output = _git("ls-tree", commit, "--", path, repo_root=repo_root)
    fields = output.split(None, 3)
    if len(fields) != 4 or fields[0] != "100644" or fields[1] != "blob" or fields[3] != path:
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"E0-MS Git mode/path drifted: {path}"
        )


def _git_blob_record(
    commit: str,
    path: str,
    *,
    role: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    _require_git_mode_100644(commit, path, repo_root=repo_root)
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=_root(repo_root),
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"E0-MS cannot reconstruct Git blob: {path}"
        )
    return {
        "path": path,
        "role": role,
        "bytes": len(result.stdout),
        "sha256": _sha256_bytes(result.stdout),
    }


def _validate_h_component_records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Mapping):
        raise AnfisAblationSequenceDevelopmentPatchError("E0-MS H payload is absent")
    components = value.get("components")
    paths = value.get("paths")
    if (
        value.get("base_commit") != PATCH_BASE_COMMIT
        or value.get("added_count") != 10
        or value.get("modified_count") != 0
        or value.get("deleted_count") != 0
        or paths != list(PATCH_PATHS)
        or value.get("paths_sha256") != _path_digest(PATCH_PATHS)
        or not isinstance(components, list)
        or len(components) != len(PATCH_PATHS)
    ):
        raise AnfisAblationSequenceDevelopmentPatchError("E0-MS H scope drifted")
    normalized: list[dict[str, Any]] = []
    for record, path in zip(components, PATCH_PATHS, strict=True):
        _validate_record_shape(
            record,
            expected_path=path,
            expected_role=PATCH_COMPONENT_ROLES[path],
        )
        if not isinstance(record, Mapping):
            raise AnfisAblationSequenceDevelopmentPatchError(
                f"E0-MS H component is not a mapping: {path}"
            )
        normalized.append(dict(cast(Mapping[str, Any], record)))
    if value.get("components_sha256") != _record_digest(normalized):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS H component digest drifted"
        )
    return normalized


def _reconstruct_h_components(
    payload: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> list[dict[str, Any]]:
    repository = payload.get("repository")
    if not isinstance(repository, Mapping):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS repository binding is absent"
        )
    head = repository.get("head")
    if not isinstance(head, str):
        raise AnfisAblationSequenceDevelopmentPatchError("E0-MS H head is absent")
    if _single_parent(head, repo_root=repo_root) != PATCH_BASE_COMMIT:
        raise AnfisAblationSequenceDevelopmentPatchError("E0-MS H parent drifted")
    expected_entries = [{"status": "A", "path": path} for path in PATCH_PATHS]
    observed = sorted(
        _observed_diff_entries(PATCH_BASE_COMMIT, head, repo_root=repo_root),
        key=lambda item: item["path"],
    )
    if observed != expected_entries:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "H-E0-MS is not exactly ten additions"
        )
    reconstructed = [
        _git_blob_record(
            head,
            path,
            role=PATCH_COMPONENT_ROLES[path],
            repo_root=repo_root,
        )
        for path in PATCH_PATHS
    ]
    for record in reconstructed:
        current = _file_record(
            Path(record["path"]),
            role=str(record["role"]),
            repo_root=repo_root,
        )
        if current != record:
            raise AnfisAblationSequenceDevelopmentPatchError(
                f"E0-MS H component differs from Git: {record['path']}"
            )
    return reconstructed


def _runtime_contract_binding(
    runtime: Mapping[str, Any],
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
        "roles": dict(runtime["roles"]),
        "denominators": dict(runtime["denominators"]),
        "features": dict(runtime["features"]),
        "bundles": dict(runtime["bundles"]),
        "outputs": dict(runtime["outputs"]),
    }


def _m0_progression_binding(*, repo_root: Path | None = None) -> dict[str, Any]:
    _validate_progression_manifests(repo_root=repo_root)
    return {
        "published_commit": PATCH_BASE_COMMIT,
        "manifest": _file_record(
            Path("reports/closure_v1/02_models/M0/manifest.json"),
            role="m0_manifest",
            repo_root=repo_root,
        ),
        "verified": True,
    }


def _derived_prelock_binding(
    runtime: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = _root(repo_root)
    namespace = anfis_ablation_sequence_output_namespace_absence(
        runtime,
        repo_root=root,
    )
    e0_m_present = [path for path in E0_M_PATHS if _lexists(root / path)]
    outcome_present = _lexists(root / OUTCOME_ACCESS_LOG)
    p_temporaries = (
        Path(f"{DEFAULT_PATCH_LOCK_PATH.as_posix()}.tmp"),
        Path(f"{DEFAULT_PATCH_MANIFEST_PATH.as_posix()}.tmp"),
    )
    if e0_m_present or outcome_present:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-M or outcome-access log exists before E0-MS"
        )
    if any(_lexists(root / path) for path in p_temporaries):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS P temporary output exists"
        )
    if _lexists(root / LOCKER_GUARD_PATH):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS locker guard remains active"
        )
    return {
        "m0_progression": _m0_progression_binding(repo_root=root),
        "output_namespace": namespace,
        "control_namespace": {
            "p_lock_path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "p_lock_absent": True,
            "p_manifest_path": DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
            "p_manifest_absent": True,
            "p_lock_temporary_absent": True,
            "p_manifest_temporary_absent": True,
            "p_guard_path": LOCKER_GUARD_PATH.as_posix(),
            "p_guard_absent": True,
        },
        "target_artifact_inputs": [],
        "target_columns_scanned": [],
        "e0_m_paths_present": 0,
        "outcome_access_log_present": False,
        "outputs_written": False,
        "verification_commands_run": False,
        "dvc_commands_run": False,
        "scientific_network_calls_made": False,
        "future_outcomes_accessed": False,
    }


def collect_anfis_ablation_sequence_development_patch_prelock_state(
    *,
    repo_root: Path | None = None,
    verify_remote: bool = True,
) -> dict[str, Any]:
    """Collect exact published H state without sequence/data execution."""
    if verify_remote is not True:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS requires live remote verification"
        )
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
        raise AnfisAblationSequenceDevelopmentPatchError(
            "Published H-E0-MS topology/ref alignment drifted"
        )
    if _git("status", "--porcelain=v1", "--untracked-files=all", repo_root=root):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS H repository must be clean"
        )
    entries = sorted(
        _observed_diff_entries(PATCH_BASE_COMMIT, head, repo_root=root),
        key=lambda item: item["path"],
    )
    expected_entries = [{"status": "A", "path": path} for path in PATCH_PATHS]
    if entries != expected_entries:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "H-E0-MS is not exactly ten additions"
        )
    components = [
        _file_record(
            Path(path),
            role=PATCH_COMPONENT_ROLES[path],
            repo_root=root,
        )
        for path in PATCH_PATHS
    ]
    runtime = load_and_validate_anfis_ablation_sequence_development_runtime(
        repo_root=root,
        verify_physical_pins=False,
    )
    physical_inputs = _verify_runtime_physical_pins(runtime, repo_root=root)
    _require_prelock_control_namespace_absent(repo_root=root)
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
            "added_count": 10,
            "modified_count": 0,
            "deleted_count": 0,
            "paths": list(PATCH_PATHS),
            "paths_sha256": _path_digest(PATCH_PATHS),
            "components": components,
            "components_sha256": _record_digest(components),
        },
        "runtime_contract": _runtime_contract_binding(
            runtime,
            runtime_record=runtime_record,
            physical_inputs=physical_inputs,
        ),
        "prelock": _derived_prelock_binding(runtime, repo_root=root),
    }


def build_anfis_ablation_sequence_development_patch_lock_payload(
    prelock: Mapping[str, Any],
    verification: Mapping[str, Any],
    *,
    created_at_utc: str,
) -> dict[str, Any]:
    """Build the unpublished lock; no execution flag becomes effective."""
    return {
        "lock_version": LOCK_VERSION,
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "experiment_id": EXPERIMENT_ID,
        "surface_id": SURFACE_ID,
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
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS lock timestamp must be a string"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS lock timestamp is malformed"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS lock timestamp must include timezone"
        )


def _validate_command_evidence(
    value: Any,
    *,
    expected_command: Sequence[str],
    context: str,
    exact_stdout: str | None = None,
) -> None:
    expected_keys = {
        "command",
        "returncode",
        "stdout_sha256",
        "stderr_sha256",
        "stdout_line_count",
        "stderr_line_count",
    }
    if not isinstance(value, Mapping) or set(value) != expected_keys:
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"E0-MS {context} evidence dialect drifted"
        )
    if value.get("command") != list(expected_command) or value.get("returncode") != 0:
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"E0-MS {context} command/result drifted"
        )
    for key in ("stdout_sha256", "stderr_sha256"):
        digest = value.get(key)
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise AnfisAblationSequenceDevelopmentPatchError(
                f"E0-MS {context} digest drifted"
            )
    for key in ("stdout_line_count", "stderr_line_count"):
        if not isinstance(value.get(key), int) or int(value[key]) < 0:
            raise AnfisAblationSequenceDevelopmentPatchError(
                f"E0-MS {context} line count drifted"
            )
    if (
        value.get("stderr_sha256") != _sha256_bytes(b"")
        or value.get("stderr_line_count") != 0
    ):
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"E0-MS {context} stderr evidence drifted"
        )
    if exact_stdout is not None and (
        value.get("stdout_sha256") != _sha256_bytes(exact_stdout.encode("utf-8"))
        or value.get("stdout_line_count") != len(exact_stdout.splitlines())
    ):
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"E0-MS {context} stdout evidence drifted"
        )


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
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS verification bundle drifted"
        )
    expected_preflight = preflight_anfis_ablation_sequence_development_patch_schema(
        repo_root=repo_root
    )
    if value.get("schema_preflight") != expected_preflight:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS schema preflight evidence drifted"
        )
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
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS focused evidence is absent"
        )
    common_keys = {
        "command",
        "returncode",
        "stdout_sha256",
        "stderr_sha256",
        "stdout_line_count",
        "stderr_line_count",
    }
    common = {key: focused.get(key) for key in common_keys}
    _validate_command_evidence(
        common,
        expected_command=FOCUSED_TEST_COMMAND,
        context="focused tests",
    )
    if set(focused) != {*common_keys, "test_count", "skipped_count", "deselected_count"}:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS focused summary dialect drifted"
        )
    if FOCUSED_TEST_COUNT < 1 or (
        focused.get("test_count") != FOCUSED_TEST_COUNT
        or focused.get("skipped_count") != 0
        or focused.get("deselected_count") != 0
    ):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS focused summary drifted"
        )


def _validate_repository_binding(
    value: Any,
    *,
    repo_root: Path | None = None,
) -> str:
    expected_keys = {
        "head",
        "parent",
        "branch",
        "tracking_ref",
        "tracking_head",
        "remote_head",
        "remote_observation_mode",
        "worktree_status",
    }
    if not isinstance(value, Mapping) or set(value) != expected_keys:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS repository dialect drifted"
        )
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
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS repository binding drifted"
        )
    if _single_parent(h_head, repo_root=repo_root) != PATCH_BASE_COMMIT:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS locked H parent drifted"
        )
    root = _root(repo_root)
    current_head = _git("rev-parse", "HEAD", repo_root=root)
    current_branch = _git("branch", "--show-current", repo_root=root)
    current_tracking = _git("rev-parse", PUBLISHED_REF, repo_root=root)
    current_remote = _live_remote_main_head(repo_root=root)
    if current_branch != "main":
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS current branch drifted"
        )
    status = _git("status", "--porcelain=v1", "--untracked-files=all", repo_root=root)
    status_paths = {line[3:] for line in status.splitlines() if len(line) >= 4}
    if current_head == h_head:
        if current_tracking != h_head or current_remote != h_head:
            raise AnfisAblationSequenceDevelopmentPatchError(
                "E0-MS current H refs drifted"
            )
        allowed = {
            DEFAULT_PATCH_LOCK_PATH.as_posix(),
            DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
        }
        if status_paths.difference(allowed):
            raise AnfisAblationSequenceDevelopmentPatchError(
                "E0-MS H worktree contains unrelated changes"
            )
    else:
        if _single_parent(current_head, repo_root=root) != h_head:
            raise AnfisAblationSequenceDevelopmentPatchError(
                "E0-MS current commit is outside H/P topology"
            )
        if current_tracking != current_head or current_remote != current_head:
            raise AnfisAblationSequenceDevelopmentPatchError(
                "E0-MS published P refs drifted"
            )
        allowed_progression_paths = {
            path
            for path in ABLATION_SEQUENCE_FINAL_PATHS
            if not path.endswith(".parquet")
        }
        allowed_progression_paths.update(ABLATION_SEQUENCE_POINTER_PATHS)
        if status_paths.difference(allowed_progression_paths):
            raise AnfisAblationSequenceDevelopmentPatchError(
                "E0-MS P worktree contains unrelated changes"
            )
    return h_head


def _sealed_output_namespace_claim(
    runtime: Mapping[str, Any],
) -> dict[str, Any]:
    finals = ablation_sequence_final_paths(runtime)
    temporaries = tuple(f"{path}.tmp" for path in finals)
    pointers = _ablation_sequence_pointer_paths(runtime)
    pointer_temporaries = tuple(f"{path}.tmp" for path in pointers)
    guards = _ablation_sequence_guard_paths(runtime)
    return {
        "final_path_count": 18,
        "final_paths": list(finals),
        "final_paths_sha256": _path_digest(finals),
        "present_final_count": 0,
        "absent_final_count": 18,
        "temporary_path_count": 18,
        "temporary_paths": list(temporaries),
        "temporary_paths_sha256": _path_digest(temporaries),
        "present_temporary_count": 0,
        "pointer_path_count": 6,
        "pointer_paths": list(pointers),
        "pointer_paths_sha256": _path_digest(pointers),
        "present_pointer_count": 0,
        "pointer_temporary_path_count": 6,
        "pointer_temporary_paths": list(pointer_temporaries),
        "pointer_temporary_paths_sha256": _path_digest(pointer_temporaries),
        "present_pointer_temporary_count": 0,
        "guard_path_count": 6,
        "guard_paths": list(guards),
        "guard_paths_sha256": _path_digest(guards),
        "present_guard_count": 0,
    }


def _sealed_prelock_binding(
    runtime: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    return {
        "m0_progression": _m0_progression_binding(repo_root=repo_root),
        "output_namespace": _sealed_output_namespace_claim(runtime),
        "control_namespace": {
            "p_lock_path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "p_lock_absent": True,
            "p_manifest_path": DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
            "p_manifest_absent": True,
            "p_lock_temporary_absent": True,
            "p_manifest_temporary_absent": True,
            "p_guard_path": LOCKER_GUARD_PATH.as_posix(),
            "p_guard_absent": True,
        },
        "target_artifact_inputs": [],
        "target_columns_scanned": [],
        "e0_m_paths_present": 0,
        "outcome_access_log_present": False,
        "outputs_written": False,
        "verification_commands_run": False,
        "dvc_commands_run": False,
        "scientific_network_calls_made": False,
        "future_outcomes_accessed": False,
    }


def validate_anfis_ablation_sequence_development_patch_lock_payload(
    payload: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    schema = _load_regular_json(
        DEFAULT_PATCH_LOCK_SCHEMA,
        context="E0-MS lock schema",
        repo_root=repo_root,
    )
    try:
        validate_json_schema(payload, schema)
    except ClosureContractError as exc:
        raise AnfisAblationSequenceDevelopmentPatchError(str(exc)) from exc
    _validate_timestamp(payload.get("created_at_utc"))
    if payload.get("authorizations") != UNPUBLISHED_AUTHORIZATIONS:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "Unpublished E0-MS authorizations drifted"
        )
    if payload.get("seals") != PATCH_SEALS:
        raise AnfisAblationSequenceDevelopmentPatchError("E0-MS seals drifted")
    h_head = _validate_repository_binding(payload.get("repository"), repo_root=repo_root)
    h_patch = payload.get("h_patch")
    h_components = _validate_h_component_records(h_patch)
    reconstructed = _reconstruct_h_components(payload, repo_root=repo_root)
    if reconstructed != h_components:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS H reconstruction drifted"
        )
    runtime = load_and_validate_anfis_ablation_sequence_development_runtime(
        repo_root=repo_root,
        verify_physical_pins=False,
    )
    physical_inputs = _verify_runtime_physical_pins(runtime, repo_root=repo_root)
    runtime_record = next(
        record
        for record in h_components
        if record["path"] == DEFAULT_RUNTIME_PATH.as_posix()
    )
    expected_runtime = _runtime_contract_binding(
        runtime,
        runtime_record=runtime_record,
        physical_inputs=physical_inputs,
    )
    if payload.get("runtime_contract") != expected_runtime:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS complete runtime binding drifted"
        )
    if payload.get("prelock") != _sealed_prelock_binding(runtime, repo_root=repo_root):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS complete prelock binding drifted"
        )
    if h_head != payload["repository"]["tracking_head"]:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS repository/H binding drifted"
        )
    _validate_verification_binding(payload.get("verification"), repo_root=repo_root)
    return dict(payload)


def _expected_companion(
    payload: Mapping[str, Any],
    lock_record: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    del repo_root
    h_components = _validate_h_component_records(payload.get("h_patch"))
    runtime_contract = payload.get("runtime_contract")
    if not isinstance(runtime_contract, Mapping):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "Cannot construct E0-MS companion runtime inputs"
        )
    physical_inputs = runtime_contract.get("physical_inputs")
    if not isinstance(physical_inputs, list):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "Cannot construct E0-MS physical inputs"
        )
    inputs = [dict(record) for record in (*h_components, *physical_inputs)]
    inputs.sort(key=lambda record: str(record.get("path")))
    paths = [str(record.get("path")) for record in inputs]
    if len(inputs) != EXPECTED_COMPANION_INPUT_COUNT or len(set(paths)) != len(inputs):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS companion must bind exactly 54 unique physical inputs"
        )
    locker_path = (
        "src/experiments/lock_closure_anfis_ablation_sequence_development_patch.py"
    )
    locker_record = next(
        dict(record) for record in h_components if record["path"] == locker_path
    )
    normalized_lock = dict(lock_record)
    if (
        set(normalized_lock) != {"path", "role", "bytes", "sha256"}
        or normalized_lock.get("path") != DEFAULT_PATCH_LOCK_PATH.as_posix()
        or normalized_lock.get("role")
        != "anfis_ablation_sequence_development_patch_lock"
    ):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS lock output record drifted"
        )
    return {
        "manifest_version": (
            "closure_anfis_ablation_sequence_development_patch_lock_manifest_v1"
        ),
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
        role="anfis_ablation_sequence_development_patch_lock",
        repo_root=repo_root,
    )
    companion = _load_regular_json(
        DEFAULT_PATCH_MANIFEST_PATH,
        context="E0-MS companion",
        repo_root=repo_root,
    )
    if _read_regular_bytes(DEFAULT_PATCH_MANIFEST_PATH, repo_root=repo_root) != _canonical_json(companion):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS companion is not canonical JSON"
        )
    expected = _expected_companion(payload, lock_record, repo_root=repo_root)
    if companion != expected:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS companion drifted"
        )
    companion_record = _file_record(
        DEFAULT_PATCH_MANIFEST_PATH,
        role="anfis_ablation_sequence_development_patch_lock_manifest",
        repo_root=repo_root,
    )
    return lock_record, companion, companion_record


def _plain_file_record(
    path: Path,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Return the writer dialect used by input/output bundle manifests."""
    payload = _read_regular_bytes(path, repo_root=repo_root)
    return {
        "path": path.as_posix(),
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
    }


def _validate_p_publication(
    payload: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
    verify_remote: bool = True,
) -> dict[str, Any]:
    """Prove the exact published P commit while tolerating only bundle prefix files."""
    if verify_remote is not True:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS requires live remote verification"
        )
    root = _root(repo_root)
    repository = payload.get("repository")
    if not isinstance(repository, Mapping):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS repository binding is absent"
        )
    h_head = repository.get("head")
    if not isinstance(h_head, str):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS H head is absent"
        )
    head = _git("rev-parse", "HEAD", repo_root=root)
    parent = _single_parent(head, repo_root=root)
    tracking = _git("rev-parse", PUBLISHED_REF, repo_root=root)
    remote = _live_remote_main_head(repo_root=root)
    if (
        parent != h_head
        or _git("branch", "--show-current", repo_root=root) != "main"
        or tracking != head
        or remote != head
    ):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "Published P-E0-MS topology/ref alignment drifted"
        )
    expected = sorted(
        (
            {"status": "A", "path": DEFAULT_PATCH_LOCK_PATH.as_posix()},
            {"status": "A", "path": DEFAULT_PATCH_MANIFEST_PATH.as_posix()},
        ),
        key=lambda item: item["path"],
    )
    observed = sorted(
        _observed_diff_entries(h_head, head, repo_root=root),
        key=lambda item: item["path"],
    )
    if observed != expected:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "P-E0-MS is not exactly lock plus companion"
        )
    for path in (DEFAULT_PATCH_LOCK_PATH, DEFAULT_PATCH_MANIFEST_PATH):
        _require_git_mode_100644(head, path.as_posix(), repo_root=root)
    reconstructed = _reconstruct_h_components(payload, repo_root=root)
    if reconstructed != _validate_h_component_records(payload.get("h_patch")):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "Published E0-MS H components drifted"
        )
    runtime = load_and_validate_anfis_ablation_sequence_development_runtime(
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
        raise AnfisAblationSequenceDevelopmentPatchError(
            "Published E0-MS physical inputs drifted"
        )
    if any(_lexists(root / path) for path in E0_M_PATHS):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-M exists before ANFIS-ablation sequence materialization"
        )
    if _lexists(root / OUTCOME_ACCESS_LOG):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "Outcome access log exists before ANFIS-ablation sequence materialization"
        )
    return {
        "h_patch_head": h_head,
        "p_patch_head": head,
        "remote_head": remote,
    }


def _slot_index(model_id: str, base_seed: int | None) -> int:
    if model_id == "A0":
        if base_seed is not None:
            raise AnfisAblationSequenceDevelopmentPatchError(
                "A0 requires base_seed=null"
            )
        return 0
    if (
        model_id != "A1"
        or isinstance(base_seed, bool)
        or not isinstance(base_seed, int)
        or base_seed not in REGISTERED_SEEDS
    ):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS target slot is not registered"
        )
    return 1 + REGISTERED_SEEDS.index(base_seed)


def _slot_namespace(model_id: str, base_seed: int | None) -> dict[str, str]:
    _slot_index(model_id, base_seed)
    if model_id == "A0":
        sequence = "data/closure_v1/development/sequences/A0/raw_no_current.parquet"
        stem = "reports/closure_v1/01_surface/sequences/A0/raw_no_current"
        guard = "tmp/closure_v1_anfis_ablation_sequences/A0_raw_no_current.guard"
    else:
        sequence = (
            "data/closure_v1/development/sequences/A1/"
            f"seed_{base_seed}.parquet"
        )
        stem = (
            "reports/closure_v1/01_surface/sequences/A1/"
            f"seed_{base_seed}"
        )
        guard = (
            "tmp/closure_v1_anfis_ablation_sequences/"
            f"A1_seed_{base_seed}.guard"
        )
    return {
        "sequence": sequence,
        "summary": f"{stem}_summary.csv",
        "manifest": f"{stem}_manifest.json",
        "pointer": f"{sequence}.dvc",
        "guard": guard,
    }


def _validate_manifest_file_record(
    value: Any,
    *,
    expected_path: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"path", "bytes", "sha256"}:
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"E0-MS bundle record dialect drifted: {expected_path}"
        )
    actual = _plain_file_record(Path(expected_path), repo_root=repo_root)
    if dict(value) != actual:
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"E0-MS bundle record drifted: {expected_path}"
        )
    return actual


def _expected_manifest_authority(
    static_authority: Mapping[str, Any],
    *,
    model_id: str,
    base_seed: int | None,
    completed_prefix_count: int,
) -> dict[str, Any]:
    keys = (
        "gate",
        "status",
        "h_patch_head",
        "p_patch_head",
        "runtime",
        "lock",
        "companion",
        "h_components_sha256",
        "physical_inputs_sha256",
        "builder_sha256",
        "auditor_sha256",
    )
    authority = {key: static_authority[key] for key in keys}
    authority.update(
        {
            "authorized_model_id": model_id,
            "authorized_base_seed": base_seed,
            "completed_prefix_count": completed_prefix_count,
        }
    )
    return authority


def _validate_bundle_counts(value: Any) -> None:
    expected_keys = {
        "common_rows",
        "intent_origins",
        "development_locations",
        "source_ids",
        "successful_origins",
        "failed_origins",
        "role_counts",
        "status_counts",
        "failure_reason_counts",
        "observed_raw_value_counts",
        "masked_raw_value_counts",
    }
    if not isinstance(value, Mapping) or set(value) != expected_keys:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS bundle count dialect drifted"
        )
    successful = value.get("successful_origins")
    failed = value.get("failed_origins")
    if (
        value.get("common_rows") != 29196
        or value.get("intent_origins") != 9732
        or value.get("development_locations") != 353
        or value.get("source_ids") != ["wqp"]
        or isinstance(successful, bool)
        or not isinstance(successful, int)
        or isinstance(failed, bool)
        or not isinstance(failed, int)
        or successful < 0
        or failed < 0
        or successful + failed != 9732
        or value.get("role_counts")
        != {"training": 8352, "model_selection": 1061, "calibration_threshold": 319}
    ):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS bundle denominators drifted"
        )
    statuses = value.get("status_counts")
    failures = value.get("failure_reason_counts")
    if (
        not isinstance(statuses, Mapping)
        or not set(statuses).issubset(ROW_STATUS_VALUES)
        or any(isinstance(count, bool) or not isinstance(count, int) or count < 0 for count in statuses.values())
        or sum(statuses.values()) != 9732
        or statuses.get("success", 0) != successful
        or sum(statuses.get(key, 0) for key in ROW_STATUS_VALUES[1:]) != failed
        or not isinstance(failures, Mapping)
        or any(
            not isinstance(reason, str)
            or not reason
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 1
            for reason, count in failures.items()
        )
        or sum(failures.values()) != failed
    ):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS bundle availability counts drifted"
        )
    observed = value.get("observed_raw_value_counts")
    masked = value.get("masked_raw_value_counts")
    expected_raw = set(RAW_MEAN_COLUMNS)
    if (
        not isinstance(observed, Mapping)
        or not isinstance(masked, Mapping)
        or set(observed) != expected_raw
        or set(masked) != expected_raw
        or any(
            isinstance(count, bool) or not isinstance(count, int) or count < 0
            for count in (*observed.values(), *masked.values())
        )
        or any(observed[column] + masked[column] != successful * 12 for column in RAW_MEAN_COLUMNS)
    ):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS raw-mask counts drifted"
        )


def _validate_materialized_bundle(
    model_id: str,
    base_seed: int | None,
    *,
    completed_prefix_count: int,
    static_authority: Mapping[str, Any],
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Validate one already-built triple without opening its Parquet columns."""
    root = _root(repo_root)
    slot = _slot_namespace(model_id, base_seed)
    manifest = _load_regular_json(
        Path(slot["manifest"]),
        context=f"E0-MS {model_id}/{base_seed} bundle manifest",
        repo_root=root,
    )
    _validate_timestamp(manifest.get("generated_at_utc"))
    expected_top = {
        "manifest_version",
        "status",
        "generated_at_utc",
        "experiment_id",
        "surface_id",
        "model_id",
        "base_seed",
        "upstream_state_seed",
        "future_outcomes_accessed",
        "targets_read",
        "evaluation_authorized",
        "e0_m_authorized",
        "e0_u_authorized",
        "dvc_command_executed",
        "horizons_months",
        "tensor_contract",
        "identity_columns",
        "canonical_sort",
        "counts",
        "authority",
        "script",
        "inputs",
        "source_code",
        "outputs",
        "completion_marker_written_last",
    }
    expected_seed = base_seed if model_id == "A1" else None
    if (
        set(manifest) != expected_top
        or next(reversed(manifest), None) != "completion_marker_written_last"
        or manifest.get("manifest_version")
        != "closure_anfis_ablation_sequence_manifest_v1"
        or manifest.get("status") != "completed"
        or manifest.get("experiment_id") != EXPERIMENT_ID
        or manifest.get("surface_id") != SURFACE_ID
        or manifest.get("model_id") != model_id
        or manifest.get("base_seed") != expected_seed
        or manifest.get("upstream_state_seed") != expected_seed
        or manifest.get("future_outcomes_accessed") is not False
        or manifest.get("targets_read") is not False
        or manifest.get("evaluation_authorized") is not False
        or manifest.get("e0_m_authorized") is not False
        or manifest.get("e0_u_authorized") is not False
        or manifest.get("dvc_command_executed") is not False
        or manifest.get("horizons_months") != [1, 2, 3]
        or manifest.get("identity_columns") != list(IDENTITY_COLUMNS)
        or manifest.get("canonical_sort")
        != ["source_id", "site_id", "origin_year_month", "common_origin_id"]
        or manifest.get("completion_marker_written_last") is not True
    ):
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"E0-MS {model_id}/{base_seed} manifest identity drifted"
        )
    tensor = manifest.get("tensor_contract")
    expected_columns = list(A0_INPUT_COLUMNS if model_id == "A0" else A1_INPUT_COLUMNS)
    expected_tensor = {
        "history_length_months": 12,
        "input_only": True,
        "target_columns": [],
        "input_columns": expected_columns,
        "input_dimension": len(expected_columns),
        "physical_type": "fixed_size_list<float32>[12]",
        "raw_mean_columns": list(RAW_MEAN_COLUMNS),
        "raw_n_obs_columns": list(RAW_N_OBS_COLUMNS),
        "raw_value_columns": list(RAW_VALUE_COLUMNS),
        "raw_mask_columns": list(RAW_MASK_COLUMNS),
        "raw_observed_rule": "finite_mean_and_finite_n_obs_greater_than_zero",
        "raw_missing_transport_value": 0.0,
        "raw_missing_transport_semantics": "transport_only_not_imputation",
        "raw_mask_values": [0.0, 1.0],
        "adaptive_state_source_mapping": (
            A1_STATE_SOURCE_MAPPING if model_id == "A1" else {}
        ),
        "adaptive_state_fallback": "forbidden",
        "failed_row_tensor_parent": "null",
    }
    if tensor != expected_tensor:
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"E0-MS {model_id}/{base_seed} tensor contract drifted"
        )
    _validate_bundle_counts(manifest.get("counts"))
    expected_authority = _expected_manifest_authority(
        static_authority,
        model_id=model_id,
        base_seed=base_seed,
        completed_prefix_count=completed_prefix_count,
    )
    if manifest.get("authority") != expected_authority:
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"E0-MS {model_id}/{base_seed} authority binding drifted"
        )
    builder_path = "src/experiments/build_closure_anfis_ablation_sequences.py"
    builder_record = _plain_file_record(Path(builder_path), repo_root=root)
    if (
        manifest.get("script") != builder_record
        or manifest.get("source_code") != [builder_record]
    ):
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"E0-MS {model_id}/{base_seed} builder binding drifted"
        )
    input_paths = [
        "data/closure_v1/common_origin_manifest.parquet",
        "data/closure_v1/common_origin_manifest.parquet.dvc",
        "reports/closure_v1/01_surface/common_origin_manifest.json",
        "data/panel/panel_monthly_v0.parquet",
        "data/panel/panel_monthly_v0.parquet.dvc",
    ]
    if model_id == "A1":
        input_paths.extend(
            (
                "data/closure_v1/development/anfis/"
                f"seed_{base_seed}/adaptive_no_current_state.parquet",
                "data/closure_v1/development/anfis/"
                f"seed_{base_seed}/adaptive_no_current_state.parquet.dvc",
                "reports/closure_v1/01_surface/anfis/"
                f"seed_{base_seed}/manifest.json",
            )
        )
    expected_inputs = [
        _plain_file_record(Path(path), repo_root=root) for path in input_paths
    ]
    if manifest.get("inputs") != expected_inputs:
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"E0-MS {model_id}/{base_seed} input binding drifted"
        )
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list) or len(outputs) != 2:
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"E0-MS {model_id}/{base_seed} output binding is incomplete"
        )
    _validate_manifest_file_record(
        outputs[0], expected_path=slot["sequence"], repo_root=root
    )
    _validate_manifest_file_record(
        outputs[1], expected_path=slot["summary"], repo_root=root
    )
    return manifest


def _validate_registered_pointer(
    sequence_path: str,
    pointer_path: str,
    *,
    repo_root: Path | None = None,
) -> None:
    root = _root(repo_root)
    try:
        pointer = yaml.load(
            _read_regular_bytes(Path(pointer_path), repo_root=root),
            Loader=_UniqueSafeLoader,
        )
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"E0-MS DVC pointer is malformed: {pointer_path}"
        ) from exc
    if (
        not isinstance(pointer, Mapping)
        or set(pointer) != {"outs"}
        or not isinstance(pointer.get("outs"), list)
        or len(pointer["outs"]) != 1
        or not isinstance(pointer["outs"][0], Mapping)
        or set(pointer["outs"][0]) != {"md5", "size", "hash", "path"}
    ):
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"E0-MS DVC pointer dialect drifted: {pointer_path}"
        )
    sequence = _read_regular_bytes(Path(sequence_path), repo_root=root)
    output = pointer["outs"][0]
    if (
        output.get("md5")
        != hashlib.md5(sequence, usedforsecurity=False).hexdigest()
        or output.get("size") != len(sequence)
        or output.get("hash") != "md5"
        or output.get("path") != Path(sequence_path).name
    ):
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"E0-MS DVC pointer does not bind its Parquet: {pointer_path}"
        )


def _static_effective_authority(
    payload: Mapping[str, Any],
    publication: Mapping[str, Any],
    lock_record: Mapping[str, Any],
    companion_record: Mapping[str, Any],
) -> dict[str, Any]:
    h_patch = payload["h_patch"]
    runtime_contract = payload["runtime_contract"]
    components = h_patch["components"]

    def component_record(path: str) -> Mapping[str, Any]:
        return next(record for record in components if record["path"] == path)

    builder = component_record(
        "src/experiments/build_closure_anfis_ablation_sequences.py"
    )
    auditor = component_record(
        "src/experiments/audit_closure_anfis_ablation_sequence_bundle.py"
    )
    return {
        "gate": PATCH_GATE,
        "status": "effective_preflight_passed",
        **EFFECTIVE_AUTHORIZATIONS,
        "h_patch_head": publication["h_patch_head"],
        "p_patch_head": publication["p_patch_head"],
        "runtime": dict(runtime_contract["record"]),
        "lock": dict(lock_record),
        "companion": dict(companion_record),
        "lock_sha256": lock_record["sha256"],
        "companion_sha256": companion_record["sha256"],
        "runtime_sha256": runtime_contract["record"]["sha256"],
        "h_components_sha256": h_patch["components_sha256"],
        "physical_inputs_sha256": runtime_contract["physical_inputs_sha256"],
        "builder_sha256": builder["sha256"],
        "auditor_sha256": auditor["sha256"],
    }


def _validate_exact_bundle_prefix(
    static_authority: Mapping[str, Any],
    *,
    audit_mode: bool = False,
    repo_root: Path | None = None,
) -> int:
    root = _root(repo_root)
    present_slots: list[bool] = []
    expected_lights: set[str] = set()
    present_pointers: list[tuple[str, str]] = []
    for index, (model_id, base_seed) in enumerate(ORDERED_BUNDLE_SLOTS):
        namespace = _slot_namespace(model_id, base_seed)
        triple = tuple(namespace[key] for key in ("sequence", "summary", "manifest"))
        observed = tuple(_lexists(root / path) for path in triple)
        if any(observed) and not all(observed):
            raise AnfisAblationSequenceDevelopmentPatchError(
                f"E0-MS partial bundle triple exists: {model_id}/{base_seed}"
            )
        complete = all(observed)
        present_slots.append(complete)
        if complete:
            expected_lights.update((namespace["summary"], namespace["manifest"]))
            _validate_materialized_bundle(
                model_id,
                base_seed,
                completed_prefix_count=index,
                static_authority=static_authority,
                repo_root=root,
            )
        if _lexists(root / namespace["pointer"]):
            present_pointers.append((namespace["sequence"], namespace["pointer"]))
        for prohibited in (
            f"{namespace['pointer']}.tmp",
            namespace["guard"],
            *(f"{path}.tmp" for path in triple),
        ):
            if _lexists(root / prohibited):
                raise AnfisAblationSequenceDevelopmentPatchError(
                    f"E0-MS prohibited prefix artifact exists: {prohibited}"
                )
    prefix_count = 0
    while prefix_count < len(present_slots) and present_slots[prefix_count]:
        prefix_count += 1
    if any(present_slots[prefix_count:]):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS completed bundles do not form the exact ordered prefix"
        )
    if present_pointers:
        if (
            not audit_mode
            or prefix_count != len(ORDERED_BUNDLE_SLOTS)
            or len(present_pointers) != len(ORDERED_BUNDLE_SLOTS)
        ):
            raise AnfisAblationSequenceDevelopmentPatchError(
                "E0-MS prohibited prefix artifact: DVC pointers must be absent "
                "or form the complete post-audit set"
            )
        for sequence_path, pointer_path in present_pointers:
            _validate_registered_pointer(
                sequence_path,
                pointer_path,
                repo_root=root,
            )
            expected_lights.add(pointer_path)
    status = _git("status", "--porcelain=v1", "--untracked-files=all", repo_root=root)
    observed_lights: set[str] = set()
    for line in status.splitlines():
        allowed_statuses = {"??", "A "} if audit_mode else {"??"}
        if len(line) < 4 or line[:2] not in allowed_statuses:
            raise AnfisAblationSequenceDevelopmentPatchError(
                "E0-MS tracked worktree drifted during prefix progression"
            )
        observed_lights.add(line[3:])
    if observed_lights != expected_lights:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS untracked light-output prefix drifted"
        )
    return prefix_count


def load_and_validate_anfis_ablation_sequence_development_patch_lock(
    lock_path: Path = DEFAULT_PATCH_LOCK_PATH,
    *,
    repo_root: Path | None = None,
    require_published: bool = False,
    verify_remote: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load the immutable lock bundle and optionally prove exact P publication."""
    if lock_path != DEFAULT_PATCH_LOCK_PATH:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS requires the closed default lock path"
        )
    if verify_remote is not True:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS requires live remote verification"
        )
    preflight_anfis_ablation_sequence_development_patch_schema(repo_root=repo_root)
    payload = _load_regular_json(
        lock_path,
        context="E0-MS patch lock",
        repo_root=repo_root,
    )
    if _read_regular_bytes(lock_path, repo_root=repo_root) != _canonical_json(payload):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS lock is not canonical JSON"
        )
    validated = validate_anfis_ablation_sequence_development_patch_lock_payload(
        payload,
        repo_root=repo_root,
    )
    lock_record, _companion, companion_record = _validate_companion(
        validated,
        repo_root=repo_root,
    )
    if require_published:
        publication = _validate_p_publication(
            validated,
            repo_root=repo_root,
            verify_remote=verify_remote,
        )
    else:
        root = _root(repo_root)
        h_head = validated["repository"]["head"]
        current_head = _git("rev-parse", "HEAD", repo_root=root)
        tracking = _git("rev-parse", PUBLISHED_REF, repo_root=root)
        remote = _live_remote_main_head(repo_root=root)
        if current_head != h_head or tracking != h_head or remote != h_head:
            raise AnfisAblationSequenceDevelopmentPatchError(
                "Unpublished E0-MS H refs drifted"
            )
        anfis_ablation_sequence_output_namespace_absence(
            load_and_validate_anfis_ablation_sequence_development_runtime(
                repo_root=root,
                verify_physical_pins=True,
            ),
            repo_root=root,
        )
        publication = {
            "h_patch_head": h_head,
            "p_patch_head": "",
            "remote_head": remote,
        }
    return validated, {
        **publication,
        "lock": lock_record,
        "companion": companion_record,
        "lock_sha256": lock_record["sha256"],
        "companion_sha256": companion_record["sha256"],
    }


def load_effective_anfis_ablation_sequence_development_authority(
    model_id: str | None = None,
    base_seed: int | None = None,
    *,
    audit_current_unpublished: bool = False,
    repo_root: Path | None = None,
    verify_remote: bool = True,
) -> dict[str, Any]:
    """Validate P and return authority for exactly the next slot or its audit."""
    if not isinstance(audit_current_unpublished, bool):
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS audit mode must be boolean"
        )
    payload, publication = (
        load_and_validate_anfis_ablation_sequence_development_patch_lock(
            repo_root=repo_root,
            require_published=True,
            verify_remote=verify_remote,
        )
    )
    static = _static_effective_authority(
        payload,
        publication,
        publication["lock"],
        publication["companion"],
    )
    prefix_count = _validate_exact_bundle_prefix(
        static,
        audit_mode=audit_current_unpublished,
        repo_root=repo_root,
    )
    if model_id is None:
        if base_seed is not None or audit_current_unpublished:
            raise AnfisAblationSequenceDevelopmentPatchError(
                "E0-MS implicit target cannot carry seed/audit mode"
            )
        if prefix_count >= len(ORDERED_BUNDLE_SLOTS):
            raise AnfisAblationSequenceDevelopmentPatchError(
                "All E0-MS bundle one-shots have already been consumed"
            )
        model_id, base_seed = ORDERED_BUNDLE_SLOTS[prefix_count]
    target_index = _slot_index(model_id, base_seed)
    if audit_current_unpublished:
        target_is_valid = 0 <= target_index < prefix_count
    else:
        target_is_valid = prefix_count < len(ORDERED_BUNDLE_SLOTS) and target_index == prefix_count
    if not target_is_valid:
        action = "audit" if audit_current_unpublished else "build"
        raise AnfisAblationSequenceDevelopmentPatchError(
            f"E0-MS target is not the exact next {action} slot"
        )
    return {
        **static,
        "authorized_model_id": model_id,
        "authorized_base_seed": base_seed,
        "completed_prefix_count": (
            prefix_count if audit_current_unpublished else target_index
        ),
        "slot_creation_prefix_count": target_index,
        "audit_current_unpublished": audit_current_unpublished,
        "ordered_bundle_slots": [
            {"model_id": slot_model, "base_seed": slot_seed}
            for slot_model, slot_seed in ORDERED_BUNDLE_SLOTS
        ],
        "progression_policy": (
            "exact_completed_untracked_prefix_no_pointers_until_all_six"
        ),
    }


def require_anfis_ablation_sequence_development_authority(
    model_id: str,
    base_seed: int | None,
    *,
    repo_root: Path | None = None,
    verify_remote: bool = True,
) -> dict[str, Any]:
    """Builder gate; call as the first operation after CLI argument parsing."""
    if verify_remote is not True:
        raise AnfisAblationSequenceDevelopmentPatchError(
            "E0-MS requires live remote verification"
        )
    return load_effective_anfis_ablation_sequence_development_authority(
        model_id,
        base_seed,
        audit_current_unpublished=False,
        repo_root=repo_root,
        verify_remote=verify_remote,
    )
