#!/usr/bin/env python
"""Run the one-shot, development-only Closure V1 M0 MIFAL bundle.

The runner never opens targets or outcomes, never tunes the ecological priors,
and never invokes DVC or the network.  It emits raw, uncalibrated conservative
risk only after the published E0-MR authority has passed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import stat
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from importlib.metadata import version as distribution_version
from pathlib import Path
from typing import Any, cast

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq
import yaml
from threadpoolctl import threadpool_limits

from src.experiments.closure_development_guard import (
    assert_development_frame,
    load_development_gate,
)
from src.mifal.closure_panel_adapter import (
    EVIDENCE_GROUPS,
    FORBIDDEN_EXACT_COLUMNS,
    MINIMUM_EVIDENCE_GROUPS,
    PANEL_PHYSICAL_COLUMNS,
    PANEL_PROJECTION_COLUMNS,
    STRICT_MIFAL_VARIABLES,
    observed_evidence_groups,
    panel_row_to_closure_mifal_payload,
    payload_is_eligible,
    project_closure_panel,
    validate_projection,
)
from src.mifal.ed_t2 import MIFALConfig, MIFALEDT2, __version__ as MIFAL_VERSION


RUNTIME_PATH = Path("configs/closure_v1/mifal_development_runtime.yaml")
PATCH_LOCK_PATH = Path("reports/closure_v1/00_protocol/mifal_development_patch_lock.json")
PATCH_COMPANION_PATH = Path(
    "reports/closure_v1/00_protocol/mifal_development_patch_lock_manifest.json"
)
COMMON_PATH = Path("data/closure_v1/common_origin_manifest.parquet")
PANEL_PATH = Path("data/panel/panel_monthly_v0.parquet")
ASSIGNMENT_PATH = Path("data/closure_v1/closure_holdout_assignment.csv")
OUTCOME_ACCESS_LOG = Path("reports/closure_v1/00_protocol/outcome_access_log.jsonl")
RUNNER_SOURCE_PATH = Path("src/experiments/run_closure_mifal.py")
ADAPTER_SOURCE_PATH = Path("src/mifal/closure_panel_adapter.py")
MIFAL_CORE_PATH = Path("src/mifal/ed_t2.py")

RAW_OUTPUT_PATH = Path("data/closure_v1/development/mifal/M0/raw_scores.parquet")
MODEL_SPEC_PATH = Path("reports/closure_v1/02_models/M0/model_spec.json")
LINEAGE_AUDIT_PATH = Path("reports/closure_v1/02_models/M0/lineage_audit.json")
AVAILABILITY_PATH = Path("reports/closure_v1/02_models/M0/availability.csv")
REPORT_PATH = Path("reports/closure_v1/02_models/M0/report.md")
MANIFEST_PATH = Path("reports/closure_v1/02_models/M0/manifest.json")
GUARD_PATH = Path("tmp/closure_v1_mifal_development/mifal_bundle.guard")
FUTURE_DVC_POINTER = Path(RAW_OUTPUT_PATH.as_posix() + ".dvc")
FORBIDDEN_MODEL_NAMESPACES = (
    Path("models/closure_v1/M0"),
    Path("models/closure_v1/mifal/M0"),
)

EXPECTED_OUTPUT_PATHS = (
    RAW_OUTPUT_PATH,
    MODEL_SPEC_PATH,
    LINEAGE_AUDIT_PATH,
    AVAILABILITY_PATH,
    REPORT_PATH,
    MANIFEST_PATH,
)
EXPECTED_COMMON_ROWS = 29196
EXPECTED_INTENT_ORIGINS = 9732
EXPECTED_DEVELOPMENT_LOCATIONS = 353
TECHNICAL_SEED = 1729
MIFAL_CANDIDATE = "mifal_ed_t2_v5_defaults"
SCORE_SEMANTICS = "mifal_type2_conservative_raw_risk_uncalibrated"
SURFACE_ID = "closure_v1_wqp_adaptive_no_current_chla"
MODEL_ID = "M0"
HORIZONS = (1, 2, 3)
DEFAULT_CONFIG_BYTES = 3217
DEFAULT_CONFIG_SHA256 = "8ad6314fbd833945d9cbd3d84267f0d18a7e79a53fbd61cdea89f703e05f4ded"
EXPECTED_VARIABLE_COVERAGE = {
    "Tw": 9731,
    "TP": 7964,
    "TN": 3372,
    "Secchi": 6938,
    "Turb": 5521,
    "DOb": 9618,
}
EXPECTED_GROUP_COUNT_ORIGINS = {2: 18, 3: 505, 4: 9209}
EXPECTED_GROUP_COUNT_ROWS = {2: 54, 3: 1515, 4: 27627}
EXPECTED_ORIGINS_BY_ROLE = {
    "training": 8352,
    "model_selection": 1061,
    "calibration_threshold": 319,
}

KEY_COLUMNS = (
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
)
EXACT_KEY_COLUMNS = (
    "source_id",
    "site_id",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
)
CANONICAL_SORT_COLUMNS = (
    "source_id",
    "site_id",
    "origin_year_month",
    "horizon_months",
    "target_year_month",
    "common_origin_id",
    "evaluation_unit_id",
)

RAW_PREDICTION_COLUMNS = (
    "surface_id",
    "model_id",
    *KEY_COLUMNS,
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

RAW_ARROW_SCHEMA = pa.schema(
    [
        pa.field("surface_id", pa.string(), nullable=False),
        pa.field("model_id", pa.string(), nullable=False),
        pa.field("source_id", pa.string(), nullable=False),
        pa.field("site_id", pa.string(), nullable=False),
        pa.field("common_origin_id", pa.string(), nullable=False),
        pa.field("evaluation_unit_id", pa.string(), nullable=False),
        pa.field("holdout_group_id", pa.string(), nullable=False),
        pa.field("assignment_role", pa.string(), nullable=False),
        pa.field("time_role", pa.string(), nullable=False),
        pa.field("origin_year_month", pa.string(), nullable=False),
        pa.field("target_year_month", pa.string(), nullable=False),
        pa.field("horizon_months", pa.int16(), nullable=False),
        pa.field("technical_seed", pa.int64(), nullable=False),
        pa.field("model_seed", pa.int64(), nullable=True),
        pa.field("upstream_state_seed", pa.int64(), nullable=True),
        pa.field("candidate", pa.string(), nullable=False),
        pa.field("selected_family", pa.bool_(), nullable=False),
        pa.field("availability_status", pa.string(), nullable=False),
        pa.field("failure_reason", pa.string(), nullable=False),
        pa.field("score_semantics", pa.string(), nullable=False),
        pa.field("raw_score", pa.float64(), nullable=True),
        pa.field("predicted_bloom_probability", pa.float64(), nullable=True),
        pa.field("interval_lower", pa.float64(), nullable=True),
        pa.field("interval_upper", pa.float64(), nullable=True),
        pa.field("data_reliability", pa.float64(), nullable=True),
        pa.field("evidence_group_count", pa.int8(), nullable=False),
        pa.field("payload_variable_count", pa.int8(), nullable=False),
        pa.field("payload_variables", pa.string(), nullable=False),
    ]
)

REQUIRED_AUTHORITY_TRUE = (
    "strict_adapter_authorized",
    "mifal_one_shot_authorized",
    "m0_execution_authorized",
)
REQUIRED_AUTHORITY_FALSE = (
    "tuning_authorized",
    "target_access_authorized",
    "calibration_authorized",
    "metrics_authorized",
    "e0_m_authorized",
    "evaluation_authorized",
    "e0_u_authorized",
    "dvc_commands_authorized",
    "scientific_network_authorized",
    "outcome_access_authorized",
    "future_outcomes_accessed",
)
AUTHORITY_HASH_FIELDS = (
    "lock_sha256",
    "companion_sha256",
    "runtime_sha256",
    "h_components_sha256",
    "physical_inputs_sha256",
    "runner_sha256",
    "adapter_sha256",
    "mifal_core_sha256",
)


class ClosureMIFALRunError(RuntimeError):
    """Raised when the closed M0 development contract is violated."""


@dataclass(frozen=True)
class OwnedOutput:
    path: Path
    device: int
    inode: int
    bytes: int
    sha256: str
    directory_descriptor: int


@dataclass(frozen=True)
class OwnedGuard:
    path: Path
    device: int
    inode: int
    file_descriptor: int
    directory_descriptor: int


def raw_prediction_contract() -> dict[str, Any]:
    """Return the exact, ordered 28-column raw M0 contract."""
    dtype_names = {
        pa.string(): "string",
        pa.int8(): "int8",
        pa.int16(): "int16",
        pa.int64(): "int64",
        pa.bool_(): "bool",
        pa.float64(): "float64",
    }
    return {
        "columns": [
            {
                "name": field.name,
                "dtype": dtype_names[field.type],
                "nullable": field.nullable,
            }
            for field in RAW_ARROW_SCHEMA
        ],
        "canonical_sort_keys": list(CANONICAL_SORT_COLUMNS),
        "availability_status_values": ["success", "input_ineligible"],
        "candidate_policy": "constant_mifal_ed_t2_v5_defaults",
        "selected_family_policy": "constant_false_no_selection_or_tuning",
        "success_policy": "at_least_two_evidence_groups_and_finite_raw_interval_reliability_in_closed_unit_interval",
        "success_probability_policy": "predicted_bloom_probability_is_null_before_common_calibration",
        "ineligible_policy": "scores_interval_and_reliability_null_but_row_retained",
        "payload_variables_encoding": "comma_joined_subsequence_of_variable_order",
        "technical_seed_policy": "constant_1729",
        "model_seed_policy": "null",
        "upstream_state_seed_policy": "null",
        "execution_exception_policy": "transaction_abort_with_owned_inode_rollback",
    }


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _manifest_json_bytes(payload: Mapping[str, Any]) -> bytes:
    if not payload or tuple(payload)[-1] != "completion_marker_written_last":
        raise ClosureMIFALRunError(
            "Manifest completion marker must be the last top-level key"
        )
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def load_runtime_contract(path: Path = RUNTIME_PATH) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ClosureMIFALRunError("MIFAL runtime must be a YAML mapping")
    if payload.get("schema_version") != "closure_mifal_development_runtime_v1":
        raise ClosureMIFALRunError("Unexpected MIFAL runtime schema_version")
    if payload.get("experiment_id") != "closure_v1" or payload.get("gate") != "E0-MR":
        raise ClosureMIFALRunError("MIFAL runtime identity drifted")
    if payload.get("status") != "ready_to_lock":
        raise ClosureMIFALRunError("MIFAL runtime is not ready_to_lock")
    projection = list(validate_projection())
    adapter = payload.get("strict_adapter")
    if not isinstance(adapter, dict):
        raise ClosureMIFALRunError("MIFAL runtime strict_adapter is missing")
    if (
        adapter.get("exact_panel_projection_count") != 27
        or adapter.get("exact_panel_projection") != projection
        or adapter.get("variable_order") != list(STRICT_MIFAL_VARIABLES)
        or adapter.get("evidence_groups")
        != {name: list(values) for name, values in EVIDENCE_GROUPS.items()}
        or adapter.get("minimum_observed_evidence_groups") != MINIMUM_EVIDENCE_GROUPS
        or adapter.get("legacy_adapter_direct_import_authorized") is not False
        or adapter.get("legacy_adapter_invocation_authorized") is not False
        or adapter.get("legacy_adapter_data_projection_authorized") is not False
        or adapter.get("package_initializer_symbol_loading")
        != "incidental_non_authoritative_no_io"
        or adapter.get("target_artifact_inputs") != []
        or adapter.get("target_columns_scanned") != []
    ):
        raise ClosureMIFALRunError("MIFAL strict adapter runtime contract drifted")
    model = payload.get("model")
    if not isinstance(model, dict) or (
        model.get("core_version") != MIFAL_VERSION
        or model.get("technical_seed") != TECHNICAL_SEED
        or model.get("candidate") != MIFAL_CANDIDATE
        or model.get("score_semantics") != SCORE_SEMANTICS
        or model.get("default_config_canonical_json_bytes") != DEFAULT_CONFIG_BYTES
        or model.get("default_config_sha256") != DEFAULT_CONFIG_SHA256
        or model.get("initial_state") != [0.05, 0.35]
        or model.get("gammaM") != 0.28
        or model.get("missing_memory_fallback_interval") != [0.0, 0.35]
        or model.get("observed_memory_inputs") != []
        or model.get("observed_chlorophyll_inputs") != []
        or model.get("parameter_tuning") != "forbidden"
        or model.get("step_call")
        != {
            "dt_days_formula": "horizon_months_times_30_4375",
            "days_per_horizon_month": 30.4375,
            "assimilate": False,
            "update_state": False,
            "compute_voi": False,
        }
    ):
        raise ClosureMIFALRunError("MIFAL v5 model runtime contract drifted")
    outputs = payload.get("outputs")
    if not isinstance(outputs, dict):
        raise ClosureMIFALRunError("MIFAL output runtime contract is missing")
    expected_light = {
        "model_spec": MODEL_SPEC_PATH.as_posix(),
        "lineage_audit": LINEAGE_AUDIT_PATH.as_posix(),
        "availability": AVAILABILITY_PATH.as_posix(),
        "report": REPORT_PATH.as_posix(),
        "manifest": MANIFEST_PATH.as_posix(),
    }
    runtime_raw = outputs.get("raw_prediction_contract")
    if not isinstance(runtime_raw, dict) or (
        outputs.get("exact_final_path_count") != len(EXPECTED_OUTPUT_PATHS)
        or outputs.get("exact_raw_prediction_rows") != EXPECTED_COMMON_ROWS
        or outputs.get("raw_scores") != RAW_OUTPUT_PATH.as_posix()
        or outputs.get("light_bundle") != expected_light
        or outputs.get("manifest_written_last") is not True
        or runtime_raw != raw_prediction_contract()
    ):
        raise ClosureMIFALRunError("MIFAL raw/output runtime contract drifted")
    denominators = payload.get("denominators")
    if not isinstance(denominators, dict) or (
        denominators.get("common_origin_rows") != EXPECTED_COMMON_ROWS
        or denominators.get("intent_origins") != EXPECTED_INTENT_ORIGINS
        or denominators.get("development_locations") != EXPECTED_DEVELOPMENT_LOCATIONS
        or denominators.get("horizons_months") != list(HORIZONS)
    ):
        raise ClosureMIFALRunError("MIFAL development denominators drifted")
    authorizations = payload.get("authorizations")
    if not isinstance(authorizations, dict) or any(
        authorizations.get(name) is not False
        for name in (*REQUIRED_AUTHORITY_TRUE, *REQUIRED_AUTHORITY_FALSE)
    ) or authorizations.get("outcome_access_log_required_state") != "absent":
        raise ClosureMIFALRunError("MIFAL runtime authorizations drifted")
    return payload


def _require_effective_authority() -> dict[str, Any]:
    from src.experiments.closure_mifal_development_patch import (
        require_mifal_development_authority,
    )

    return require_mifal_development_authority(repo_root=PROJECT_ROOT)


def _validated_authority_snapshot(authority: Mapping[str, Any]) -> dict[str, Any]:
    if authority.get("gate") != "E0-MR" or authority.get("status") != "effective_preflight_passed":
        raise ClosureMIFALRunError("Published E0-MR authority identity/status drifted")
    if any(authority.get(name) is not True for name in REQUIRED_AUTHORITY_TRUE):
        raise ClosureMIFALRunError("Published E0-MR execution authority is incomplete")
    if any(authority.get(name) is not False for name in REQUIRED_AUTHORITY_FALSE):
        raise ClosureMIFALRunError("Published E0-MR authority broadened a forbidden operation")
    for name in AUTHORITY_HASH_FIELDS:
        value = authority.get(name)
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ClosureMIFALRunError(f"Published E0-MR authority hash is invalid: {name}")
    for name in ("h_patch_head", "p_patch_head"):
        value = authority.get(name)
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{40}", value) is None:
            raise ClosureMIFALRunError(f"Published E0-MR commit binding is invalid: {name}")
    if (
        authority.get("raw_prediction_contract") != raw_prediction_contract()
        or authority.get("exact_raw_prediction_rows") != EXPECTED_COMMON_ROWS
        or authority.get("minimum_observed_evidence_groups") != MINIMUM_EVIDENCE_GROUPS
    ):
        raise ClosureMIFALRunError("Published E0-MR raw/denominator binding drifted")
    names = (
        "gate",
        "status",
        *REQUIRED_AUTHORITY_TRUE,
        *REQUIRED_AUTHORITY_FALSE,
        "h_patch_head",
        "p_patch_head",
        *AUTHORITY_HASH_FIELDS,
        "raw_prediction_contract",
        "exact_raw_prediction_rows",
        "minimum_observed_evidence_groups",
    )
    return {name: authority[name] for name in names}


def _open_real_repository_parent(
    path: Path,
    *,
    create: bool,
    directory_mode: int = 0o755,
) -> tuple[int, Path]:
    try:
        repository_root = PROJECT_ROOT.resolve(strict=True)
        lexical_path = Path(os.path.abspath(path if path.is_absolute() else PROJECT_ROOT / path))
        relative_parent = lexical_path.parent.relative_to(repository_root)
    except (FileNotFoundError, ValueError) as exc:
        raise ClosureMIFALRunError(f"Path escapes the repository: {path}") from exc
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(repository_root, flags)
    except OSError as exc:
        raise ClosureMIFALRunError("Repository root cannot be opened safely") from exc
    try:
        for part in relative_parent.parts:
            try:
                named = os.stat(part, dir_fd=descriptor, follow_symlinks=False)
            except FileNotFoundError:
                if not create:
                    raise ClosureMIFALRunError(
                        f"Required repository parent is absent: {lexical_path.parent}"
                    )
                try:
                    os.mkdir(part, mode=directory_mode, dir_fd=descriptor)
                except FileExistsError:
                    pass
                named = os.stat(part, dir_fd=descriptor, follow_symlinks=False)
            if not stat.S_ISDIR(named.st_mode):
                raise ClosureMIFALRunError(
                    f"Repository ancestor is not a real directory: {lexical_path.parent}"
                )
            child = os.open(part, flags, dir_fd=descriptor)
            opened = os.fstat(child)
            if (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino):
                os.close(child)
                raise ClosureMIFALRunError(
                    f"Repository ancestor identity drifted: {lexical_path.parent}"
                )
            previous = descriptor
            descriptor = child
            os.close(previous)
        parent = lexical_path.parent.lstat()
        opened_parent = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(parent.st_mode)
            or (parent.st_dev, parent.st_ino) != (opened_parent.st_dev, opened_parent.st_ino)
        ):
            raise ClosureMIFALRunError(
                f"Repository parent identity drifted: {lexical_path.parent}"
            )
        return descriptor, lexical_path
    except BaseException:
        os.close(descriptor)
        raise


def _file_record(path: Path, *, logical_path: Path | None = None) -> dict[str, Any]:
    directory_descriptor, lexical_path = _open_real_repository_parent(path, create=False)
    descriptor: int | None = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        named_before = os.stat(
            lexical_path.name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        descriptor = os.open(lexical_path.name, flags, dir_fd=directory_descriptor)
        opened_before = os.fstat(descriptor)
        before = (
            opened_before.st_dev,
            opened_before.st_ino,
            opened_before.st_size,
            opened_before.st_mtime_ns,
            opened_before.st_ctime_ns,
        )
        if (
            not stat.S_ISREG(named_before.st_mode)
            or not stat.S_ISREG(opened_before.st_mode)
            or (named_before.st_dev, named_before.st_ino)
            != (opened_before.st_dev, opened_before.st_ino)
        ):
            raise ClosureMIFALRunError(f"Input is not one stable regular file: {path}")
        digest = hashlib.sha256()
        size = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
        opened_after = os.fstat(descriptor)
        named_after = os.stat(
            lexical_path.name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        after_open = (
            opened_after.st_dev,
            opened_after.st_ino,
            opened_after.st_size,
            opened_after.st_mtime_ns,
            opened_after.st_ctime_ns,
        )
        after_name = (
            named_after.st_dev,
            named_after.st_ino,
            named_after.st_size,
            named_after.st_mtime_ns,
            named_after.st_ctime_ns,
        )
        if before != after_open or before != after_name or size != opened_after.st_size:
            raise ClosureMIFALRunError(f"Input changed while it was hashed: {path}")
        record_path = logical_path or lexical_path.relative_to(PROJECT_ROOT)
        return {
            "path": record_path.as_posix(),
            "bytes": int(size),
            "sha256": digest.hexdigest(),
        }
    except OSError as exc:
        raise ClosureMIFALRunError(f"Input cannot be opened safely: {path}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory_descriptor)


def _unlink_name_if_owned(
    directory_descriptor: int,
    name: str,
    *,
    device: int,
    inode: int,
) -> bool:
    try:
        metadata = os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return False
    if stat.S_ISREG(metadata.st_mode) and (metadata.st_dev, metadata.st_ino) == (
        device,
        inode,
    ):
        os.unlink(name, dir_fd=directory_descriptor)
        return True
    return False


def _hash_owned_name(owned: OwnedOutput) -> tuple[int, str]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        named_before = os.stat(
            owned.path.name,
            dir_fd=owned.directory_descriptor,
            follow_symlinks=False,
        )
        descriptor = os.open(owned.path.name, flags, dir_fd=owned.directory_descriptor)
        opened_before = os.fstat(descriptor)
        expected = (owned.device, owned.inode)
        if (
            not stat.S_ISREG(named_before.st_mode)
            or not stat.S_ISREG(opened_before.st_mode)
            or (named_before.st_dev, named_before.st_ino) != expected
            or (opened_before.st_dev, opened_before.st_ino) != expected
        ):
            raise ClosureMIFALRunError(f"Owned MIFAL artifact identity drifted: {owned.path}")
        before = (
            opened_before.st_dev,
            opened_before.st_ino,
            opened_before.st_size,
            opened_before.st_mtime_ns,
            opened_before.st_ctime_ns,
        )
        digest = hashlib.sha256()
        size = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
        opened_after = os.fstat(descriptor)
        named_after = os.stat(
            owned.path.name,
            dir_fd=owned.directory_descriptor,
            follow_symlinks=False,
        )
        after_open = (
            opened_after.st_dev,
            opened_after.st_ino,
            opened_after.st_size,
            opened_after.st_mtime_ns,
            opened_after.st_ctime_ns,
        )
        after_name = (
            named_after.st_dev,
            named_after.st_ino,
            named_after.st_size,
            named_after.st_mtime_ns,
            named_after.st_ctime_ns,
        )
        if before != after_open or before != after_name or size != opened_after.st_size:
            raise ClosureMIFALRunError(f"Owned MIFAL artifact changed: {owned.path}")
        return size, digest.hexdigest()
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _write_output_no_clobber_owned(
    path: Path,
    writer: Any,
    *,
    binary: bool,
) -> OwnedOutput:
    directory_descriptor, lexical_path = _open_real_repository_parent(path, create=True)
    temporary_name = lexical_path.name + ".tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    device: int | None = None
    inode: int | None = None
    committed = False
    try:
        try:
            descriptor = os.open(
                temporary_name,
                flags,
                0o644,
                dir_fd=directory_descriptor,
            )
        except FileExistsError as exc:
            raise ClosureMIFALRunError(
                f"Refusing to overwrite temporary artifact: {path}.tmp"
            ) from exc
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ClosureMIFALRunError(f"Temporary artifact is not regular: {path}.tmp")
        device, inode = int(metadata.st_dev), int(metadata.st_ino)
        duplicate = os.dup(descriptor)
        try:
            handle = (
                os.fdopen(duplicate, "wb")
                if binary
                else os.fdopen(duplicate, "w", encoding="utf-8", newline="")
            )
        except BaseException:
            os.close(duplicate)
            raise
        with handle:
            writer(handle)
            handle.flush()
            os.fsync(handle.fileno())
        temporary = os.stat(
            temporary_name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        opened_parent = os.fstat(directory_descriptor)
        lexical_parent = lexical_path.parent.lstat()
        if (
            not stat.S_ISREG(temporary.st_mode)
            or (temporary.st_dev, temporary.st_ino) != (device, inode)
            or not stat.S_ISDIR(lexical_parent.st_mode)
            or (lexical_parent.st_dev, lexical_parent.st_ino)
            != (opened_parent.st_dev, opened_parent.st_ino)
        ):
            raise ClosureMIFALRunError(f"Temporary artifact identity drifted: {path}.tmp")
        try:
            os.link(
                temporary_name,
                lexical_path.name,
                src_dir_fd=directory_descriptor,
                dst_dir_fd=directory_descriptor,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            raise ClosureMIFALRunError(f"Refusing to overwrite final artifact: {path}") from exc
        final = os.stat(
            lexical_path.name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        if not stat.S_ISREG(final.st_mode) or (final.st_dev, final.st_ino) != (
            device,
            inode,
        ):
            _unlink_name_if_owned(
                directory_descriptor,
                lexical_path.name,
                device=device,
                inode=inode,
            )
            raise ClosureMIFALRunError(f"Final artifact identity drifted: {path}")
        if not _unlink_name_if_owned(
            directory_descriptor,
            temporary_name,
            device=device,
            inode=inode,
        ):
            _unlink_name_if_owned(
                directory_descriptor,
                lexical_path.name,
                device=device,
                inode=inode,
            )
            raise ClosureMIFALRunError(f"Temporary artifact changed: {path}.tmp")
        os.fsync(directory_descriptor)
        os.close(descriptor)
        descriptor = None
        provisional = OwnedOutput(
            lexical_path,
            device,
            inode,
            0,
            "",
            directory_descriptor,
        )
        size, sha256 = _hash_owned_name(provisional)
        committed = True
        return OwnedOutput(
            lexical_path,
            device,
            inode,
            size,
            sha256,
            directory_descriptor,
        )
    finally:
        active_error = sys.exc_info()[1]
        cleanup_errors: list[Exception] = []
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as exc:
                cleanup_errors.append(exc)
        if not committed:
            if device is not None and inode is not None:
                for name in (lexical_path.name, temporary_name):
                    try:
                        _unlink_name_if_owned(
                            directory_descriptor,
                            name,
                            device=device,
                            inode=inode,
                        )
                    except OSError as exc:
                        cleanup_errors.append(exc)
                try:
                    os.fsync(directory_descriptor)
                except OSError as exc:
                    cleanup_errors.append(exc)
            try:
                os.close(directory_descriptor)
            except OSError as exc:
                cleanup_errors.append(exc)
        if cleanup_errors:
            error = ClosureMIFALRunError("MIFAL artifact cleanup failed")
            if active_error is not None:
                raise error from active_error
            raise error from cleanup_errors[0]


def _owned_file_record(owned: OwnedOutput, *, logical_path: Path | None = None) -> dict[str, Any]:
    size, sha256 = _hash_owned_name(owned)
    if size != owned.bytes or sha256 != owned.sha256:
        raise ClosureMIFALRunError(f"Owned MIFAL output bytes drifted: {owned.path}")
    record_path = logical_path or owned.path.relative_to(PROJECT_ROOT)
    return {"path": record_path.as_posix(), "bytes": size, "sha256": sha256}


class OutputTransaction:
    """Own every published inode until the manifest-last bundle commits."""

    def __init__(self) -> None:
        self._owned: list[OwnedOutput] = []

    def __enter__(self) -> OutputTransaction:
        return self

    def _publish(self, path: Path, writer: Any, *, binary: bool) -> OwnedOutput:
        owned = _write_output_no_clobber_owned(path, writer, binary=binary)
        self._owned.append(owned)
        return owned

    def publish_bytes(self, payload: bytes, path: Path) -> OwnedOutput:
        return self._publish(path, lambda handle: handle.write(payload), binary=True)

    def publish_arrow_table(self, table: pa.Table, path: Path) -> OwnedOutput:
        return self._publish(
            path,
            lambda handle: pq.write_table(
                table,
                handle,
                compression="zstd",
                use_dictionary=False,
            ),
            binary=True,
        )

    def file_record(self, owned: OwnedOutput, *, logical_path: Path | None = None) -> dict[str, Any]:
        if owned not in self._owned:
            raise ClosureMIFALRunError("Output record is not owned by this transaction")
        return _owned_file_record(owned, logical_path=logical_path)

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        commit_error: ClosureMIFALRunError | None = None
        rollback_errors: list[Exception] = []
        if exc_type is None:
            for owned in self._owned:
                try:
                    _owned_file_record(owned)
                    opened_parent = os.fstat(owned.directory_descriptor)
                    lexical_parent = owned.path.parent.lstat()
                except (ClosureMIFALRunError, FileNotFoundError, OSError) as error:
                    commit_error = ClosureMIFALRunError(
                        f"MIFAL output disappeared before commit: {owned.path}"
                    )
                    commit_error.add_note(str(error))
                    break
                if (
                    not stat.S_ISDIR(lexical_parent.st_mode)
                    or (opened_parent.st_dev, opened_parent.st_ino)
                    != (lexical_parent.st_dev, lexical_parent.st_ino)
                ):
                    commit_error = ClosureMIFALRunError(
                        f"MIFAL output parent drifted: {owned.path.parent}"
                    )
                    break
        if exc_type is not None or commit_error is not None:
            for owned in reversed(self._owned):
                try:
                    if _unlink_name_if_owned(
                        owned.directory_descriptor,
                        owned.path.name,
                        device=owned.device,
                        inode=owned.inode,
                    ):
                        os.fsync(owned.directory_descriptor)
                except OSError as error:
                    rollback_errors.append(error)
        for owned in self._owned:
            try:
                os.close(owned.directory_descriptor)
            except OSError as error:
                if exc_type is not None or commit_error is not None:
                    rollback_errors.append(error)
        self._owned.clear()
        if rollback_errors:
            error = ClosureMIFALRunError("MIFAL output rollback failed")
            if exc is not None:
                raise error from exc
            if commit_error is not None:
                raise error from commit_error
            raise error from rollback_errors[0]
        if commit_error is not None:
            raise commit_error
        return False


def _acquire_guard() -> OwnedGuard:
    directory_descriptor, lexical_guard = _open_real_repository_parent(
        GUARD_PATH,
        create=True,
        directory_mode=0o700,
    )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    device: int | None = None
    inode: int | None = None
    try:
        try:
            descriptor = os.open(
                lexical_guard.name,
                flags,
                0o600,
                dir_fd=directory_descriptor,
            )
        except FileExistsError as exc:
            raise ClosureMIFALRunError(
                f"MIFAL development slot is already reserved: {GUARD_PATH}"
            ) from exc
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ClosureMIFALRunError("MIFAL guard is not regular")
        device, inode = int(metadata.st_dev), int(metadata.st_ino)
        opened_parent = os.fstat(directory_descriptor)
        lexical_parent = lexical_guard.parent.lstat()
        if (
            not stat.S_ISDIR(lexical_parent.st_mode)
            or (opened_parent.st_dev, opened_parent.st_ino)
            != (lexical_parent.st_dev, lexical_parent.st_ino)
        ):
            raise ClosureMIFALRunError("MIFAL guard parent identity drifted")
        os.fsync(descriptor)
        os.fsync(directory_descriptor)
        return OwnedGuard(
            lexical_guard,
            device,
            inode,
            descriptor,
            directory_descriptor,
        )
    except BaseException as exc:
        if device is not None and inode is not None:
            _unlink_name_if_owned(
                directory_descriptor,
                lexical_guard.name,
                device=device,
                inode=inode,
            )
            os.fsync(directory_descriptor)
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory_descriptor)
        raise exc


def _release_guard(guard: OwnedGuard) -> None:
    errors: list[Exception] = []
    try:
        opened_parent = os.fstat(guard.directory_descriptor)
        lexical_parent = guard.path.parent.lstat()
        named = os.stat(
            guard.path.name,
            dir_fd=guard.directory_descriptor,
            follow_symlinks=False,
        )
        if not stat.S_ISREG(named.st_mode) or (named.st_dev, named.st_ino) != (
            guard.device,
            guard.inode,
        ) or not stat.S_ISDIR(lexical_parent.st_mode) or (
            opened_parent.st_dev,
            opened_parent.st_ino,
        ) != (
            lexical_parent.st_dev,
            lexical_parent.st_ino,
        ):
            raise ClosureMIFALRunError("MIFAL guard changed during execution")
        if not _unlink_name_if_owned(
            guard.directory_descriptor,
            guard.path.name,
            device=guard.device,
            inode=guard.inode,
        ):
            raise ClosureMIFALRunError("Owned MIFAL guard disappeared")
        os.fsync(guard.directory_descriptor)
    except Exception as exc:
        errors.append(exc)
    for descriptor in (guard.file_descriptor, guard.directory_descriptor):
        try:
            os.close(descriptor)
        except OSError as exc:
            errors.append(exc)
    if errors:
        raise ClosureMIFALRunError("MIFAL guard cleanup failed") from errors[0]


def _assert_absent_namespace(*, allow_guard: bool = False) -> None:
    candidates = list(EXPECTED_OUTPUT_PATHS)
    candidates.extend(Path(path.as_posix() + ".tmp") for path in EXPECTED_OUTPUT_PATHS)
    candidates.extend((GUARD_PATH, FUTURE_DVC_POINTER, Path(FUTURE_DVC_POINTER.as_posix() + ".tmp")))
    present = [
        path.as_posix()
        for path in candidates
        if _lexists(path) and not (allow_guard and path == GUARD_PATH)
    ]
    if present:
        raise ClosureMIFALRunError(f"MIFAL output namespace is not empty: {present}")
    _assert_no_forbidden_side_effects()


def _assert_no_forbidden_side_effects() -> None:
    forbidden = [FUTURE_DVC_POINTER, Path(FUTURE_DVC_POINTER.as_posix() + ".tmp")]
    forbidden.extend(Path(path.as_posix() + ".tmp") for path in EXPECTED_OUTPUT_PATHS)
    forbidden.extend(FORBIDDEN_MODEL_NAMESPACES)
    present = [path.as_posix() for path in forbidden if _lexists(path)]
    if present:
        raise ClosureMIFALRunError(f"M0 created a forbidden side effect: {present}")
    if _lexists(OUTCOME_ACCESS_LOG):
        raise ClosureMIFALRunError("Outcome-access log must remain absent before E0-M")


def _assert_exact_published_namespace() -> None:
    expected_by_anchor = {
        RAW_OUTPUT_PATH: {RAW_OUTPUT_PATH.name},
        MANIFEST_PATH: {
            MODEL_SPEC_PATH.name,
            LINEAGE_AUDIT_PATH.name,
            AVAILABILITY_PATH.name,
            REPORT_PATH.name,
            MANIFEST_PATH.name,
        },
    }
    for anchor, expected_names in expected_by_anchor.items():
        descriptor, lexical = _open_real_repository_parent(anchor, create=False)
        try:
            observed = set(os.listdir(descriptor))
            if observed != expected_names:
                raise ClosureMIFALRunError(
                    f"M0 published namespace contains unexpected names: "
                    f"{lexical.parent}: {sorted(observed)}"
                )
            for name in observed:
                metadata = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                if not stat.S_ISREG(metadata.st_mode):
                    raise ClosureMIFALRunError(
                        f"M0 published namespace contains a non-regular final: {name}"
                    )
        finally:
            os.close(descriptor)


def _load_common_frame() -> pd.DataFrame:
    frame = pq.read_table(COMMON_PATH, columns=list(KEY_COLUMNS)).to_pandas()
    if len(frame) != EXPECTED_COMMON_ROWS:
        raise ClosureMIFALRunError("Common-origin row denominator drifted")
    if frame["common_origin_id"].nunique() != EXPECTED_INTENT_ORIGINS:
        raise ClosureMIFALRunError("Common-origin intent denominator drifted")
    if frame[list(KEY_COLUMNS)].isna().any().any() or frame.duplicated(list(EXACT_KEY_COLUMNS)).any():
        raise ClosureMIFALRunError("Common-origin identity is null or duplicated")
    if set(frame["source_id"].astype(str)) != {"wqp"}:
        raise ClosureMIFALRunError("Common-origin contains a non-WQP source")
    if set(frame["assignment_role"].astype(str)) != {"development"}:
        raise ClosureMIFALRunError("Common-origin contains a non-development assignment")
    if set(pd.to_numeric(frame["horizon_months"], errors="raise").astype(int)) != set(HORIZONS):
        raise ClosureMIFALRunError("Common-origin horizons drifted")
    if (frame["origin_year_month"].astype(str) > "2021-12").any() or (
        frame["target_year_month"].astype(str) > "2021-12"
    ).any():
        raise ClosureMIFALRunError("Common-origin materialized a post-2021 key")
    counts = frame.groupby("common_origin_id", sort=False)["horizon_months"].nunique()
    if not counts.eq(3).all():
        raise ClosureMIFALRunError("M0 requires all three horizons for every origin")
    return frame.sort_values(list(CANONICAL_SORT_COLUMNS), kind="mergesort").reset_index(drop=True)


def _load_panel_frame(development_site_ids: Sequence[str]) -> pd.DataFrame:
    validate_projection()
    dataset = ds.dataset(PANEL_PATH, format="parquet")
    predicate = (
        (ds.field("source_id") == "wqp")
        & ds.field("site_id").isin(list(development_site_ids))
        & (ds.field("year_month") <= "2021-12")
    )
    frame = dataset.scanner(
        columns=list(PANEL_PROJECTION_COLUMNS),
        filter=predicate,
    ).to_table().to_pandas()
    frame = project_closure_panel(frame)
    if frame.duplicated(["source_id", "site_id", "year_month"]).any():
        raise ClosureMIFALRunError("Panel contains duplicate M0 origin keys")
    return frame


def _payload_names(payload: Mapping[str, Any]) -> tuple[str, ...]:
    names = tuple(variable for variable in STRICT_MIFAL_VARIABLES if variable in payload)
    if set(names) != set(payload):
        raise ClosureMIFALRunError("Strict M0 payload contains an unknown variable")
    return names


def build_m0_predictions(
    common: pd.DataFrame,
    panel: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build raw M0 scores without labels, calibration, or state carry."""
    missing_common = sorted(set(KEY_COLUMNS).difference(common.columns))
    if missing_common:
        raise ClosureMIFALRunError(f"Common frame is missing keys: {missing_common}")
    panel = project_closure_panel(panel)
    panel_for_join = panel.rename(columns={"year_month": "origin_year_month"})
    joined = common.merge(
        panel_for_join,
        on=["source_id", "site_id", "origin_year_month"],
        how="left",
        validate="many_to_one",
        sort=False,
    )
    if len(joined) != len(common):
        raise ClosureMIFALRunError("M0 panel join changed the intent-to-predict denominator")
    model = MIFALEDT2()
    expected_initial_state = (0.05, 0.35)
    if model.current_state() != expected_initial_state:
        raise ClosureMIFALRunError("MIFAL v5 initial state drifted")
    rows: list[dict[str, Any]] = []
    availability_by_origin: dict[str, dict[str, Any]] = {}
    joined_columns = tuple(str(column) for column in joined.columns)
    for values in joined.itertuples(index=False, name=None):
        row_mapping = dict(zip(joined_columns, values, strict=True))
        payload = panel_row_to_closure_mifal_payload(row_mapping)
        payload_names = _payload_names(payload)
        groups = observed_evidence_groups(payload)
        eligible = payload_is_eligible(payload)
        raw_score: float | None = None
        interval_lower: float | None = None
        interval_upper: float | None = None
        data_reliability: float | None = None
        if eligible:
            result = model.step(
                payload,
                dt_days=float(row_mapping["horizon_months"]) * 30.4375,
                assimilate=False,
                update_state=False,
                compute_voi=False,
            )
            interval = cast(tuple[float, float], result["risk_interval"])
            indices = cast(Mapping[str, tuple[float, float]], result["indices"])
            fused = cast(Mapping[str, Any], result["fused"])
            if fused["Chl"].available or fused["Chl_prev"].available:
                raise ClosureMIFALRunError("M0 fused observed chlorophyll memory")
            if indices["Memory"] != (0.0, 0.35):
                raise ClosureMIFALRunError("M0 observed-memory fallback drifted")
            if result["observation_interval"] is not None:
                raise ClosureMIFALRunError("M0 unexpectedly assimilated a biological observation")
            raw_score = float(cast(float, result["risk_conservative"]))
            interval_lower = float(interval[0])
            interval_upper = float(interval[1])
            data_reliability = float(cast(float, result["data_reliability"]))
        status = "success" if eligible else "input_ineligible"
        failure = "" if eligible else "strict_non_chla_evidence_incomplete"
        record = {
            "surface_id": SURFACE_ID,
            "model_id": MODEL_ID,
            **{name: row_mapping[name] for name in KEY_COLUMNS},
            "technical_seed": TECHNICAL_SEED,
            "model_seed": None,
            "upstream_state_seed": None,
            "candidate": MIFAL_CANDIDATE,
            "selected_family": False,
            "availability_status": status,
            "failure_reason": failure,
            "score_semantics": SCORE_SEMANTICS,
            "raw_score": raw_score,
            "predicted_bloom_probability": None,
            "interval_lower": interval_lower,
            "interval_upper": interval_upper,
            "data_reliability": data_reliability,
            "payload_variable_count": len(payload_names),
            "payload_variables": ",".join(payload_names),
            "evidence_group_count": len(groups),
        }
        rows.append(record)
        origin_id = str(row_mapping["common_origin_id"])
        origin_record = {
            "common_origin_id": origin_id,
            "source_id": str(row_mapping["source_id"]),
            "site_id": str(row_mapping["site_id"]),
            "origin_year_month": str(row_mapping["origin_year_month"]),
            "time_role": str(row_mapping["time_role"]),
            "payload_variable_count": len(payload_names),
            "payload_variables": ",".join(payload_names),
            "evidence_group_count": len(groups),
            "evidence_groups": ",".join(groups),
            **{f"has_{name}": name in payload for name in STRICT_MIFAL_VARIABLES},
            **{f"has_group_{name}": name in groups for name in EVIDENCE_GROUPS},
            "availability_status": status,
            "failure_reason": failure,
        }
        previous = availability_by_origin.setdefault(origin_id, origin_record)
        if previous != origin_record:
            raise ClosureMIFALRunError("M0 availability changed across horizons")
    if model.current_state() != expected_initial_state:
        raise ClosureMIFALRunError("M0 carried state between origins")
    if len(rows) != len(common):
        raise ClosureMIFALRunError("M0 silently dropped an intent-to-predict row")
    raw = canonical_m0_raw_frame(pd.DataFrame(rows, columns=RAW_PREDICTION_COLUMNS))
    availability = pd.DataFrame(availability_by_origin.values()).sort_values(
        ["source_id", "site_id", "origin_year_month", "common_origin_id"],
        kind="mergesort",
    ).reset_index(drop=True)
    return raw, availability


def canonical_m0_raw_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if tuple(frame.columns) != RAW_PREDICTION_COLUMNS:
        raise ClosureMIFALRunError("M0 raw columns/order drifted")
    if frame.empty:
        raise ClosureMIFALRunError("M0 raw table cannot be empty")
    string_columns = [
        field.name for field in RAW_ARROW_SCHEMA if pa.types.is_string(field.type)
    ]
    if frame[string_columns].isna().any().any():
        raise ClosureMIFALRunError("M0 raw non-null string column contains nulls")
    if frame[["horizon_months", "technical_seed", "selected_family", "evidence_group_count", "payload_variable_count"]].isna().any().any():
        raise ClosureMIFALRunError("M0 raw non-null scalar column contains nulls")
    if not frame["surface_id"].eq(SURFACE_ID).all() or not frame["model_id"].eq(MODEL_ID).all():
        raise ClosureMIFALRunError("M0 raw identity drifted")
    if not frame["technical_seed"].eq(TECHNICAL_SEED).all():
        raise ClosureMIFALRunError("M0 technical seed drifted")
    if set(frame["source_id"].astype(str)) != {"wqp"} or set(
        frame["assignment_role"].astype(str)
    ) != {"development"}:
        raise ClosureMIFALRunError("M0 raw source/development assignment drifted")
    if not set(frame["time_role"].astype(str)).issubset(
        {"training", "model_selection", "calibration_threshold"}
    ):
        raise ClosureMIFALRunError("M0 raw time role drifted")
    if not set(pd.to_numeric(frame["horizon_months"], errors="raise").astype(int)).issubset(
        set(HORIZONS)
    ):
        raise ClosureMIFALRunError("M0 raw horizon drifted")
    if frame["model_seed"].notna().any() or frame["upstream_state_seed"].notna().any():
        raise ClosureMIFALRunError("Deterministic M0 cannot carry model/upstream seeds")
    if not frame["candidate"].eq(MIFAL_CANDIDATE).all() or frame["selected_family"].any():
        raise ClosureMIFALRunError("M0 default/no-selection policy drifted")
    if not frame["score_semantics"].eq(SCORE_SEMANTICS).all():
        raise ClosureMIFALRunError("M0 raw score semantics drifted")
    if frame["predicted_bloom_probability"].notna().any():
        raise ClosureMIFALRunError("Uncalibrated M0 probability must remain null")
    status = frame["availability_status"].astype(str)
    if not set(status).issubset({"success", "input_ineligible"}):
        raise ClosureMIFALRunError("M0 availability status drifted")
    success = status.eq("success")
    ineligible = status.eq("input_ineligible")
    if not frame.loc[success, "failure_reason"].eq("").all():
        raise ClosureMIFALRunError("Successful M0 rows cannot have a failure reason")
    if not frame.loc[ineligible, "failure_reason"].eq(
        "strict_non_chla_evidence_incomplete"
    ).all():
        raise ClosureMIFALRunError("Ineligible M0 failure reason drifted")
    group_count = pd.to_numeric(frame["evidence_group_count"], errors="raise")
    variable_count = pd.to_numeric(frame["payload_variable_count"], errors="raise")
    if not group_count.loc[success].ge(MINIMUM_EVIDENCE_GROUPS).all():
        raise ClosureMIFALRunError("Successful M0 row lacks two ecological groups")
    if not group_count.loc[ineligible].lt(MINIMUM_EVIDENCE_GROUPS).all():
        raise ClosureMIFALRunError("Ineligible M0 row unexpectedly has enough groups")
    if not variable_count.between(0, len(STRICT_MIFAL_VARIABLES)).all() or not group_count.between(
        0, len(EVIDENCE_GROUPS)
    ).all():
        raise ClosureMIFALRunError("M0 payload/group count leaves its contract")
    numeric = ("raw_score", "interval_lower", "interval_upper", "data_reliability")
    for name in numeric:
        values = pd.to_numeric(frame[name], errors="coerce")
        if values.loc[success].isna().any() or values.loc[ineligible].notna().any():
            raise ClosureMIFALRunError(f"M0 {name} nullability drifted")
        if not values.loc[success].between(0.0, 1.0).all():
            raise ClosureMIFALRunError(f"M0 {name} leaves [0, 1]")
    if not (
        frame.loc[success, "interval_lower"]
        <= frame.loc[success, "raw_score"]
    ).all() or not (
        frame.loc[success, "raw_score"]
        <= frame.loc[success, "interval_upper"]
    ).all():
        raise ClosureMIFALRunError("M0 conservative score leaves its interval")
    forbidden_tokens = ("chl", "chlorophyll", "risk_chla")
    if frame["payload_variables"].astype(str).str.lower().map(
        lambda value: any(token in value for token in forbidden_tokens)
    ).any():
        raise ClosureMIFALRunError("M0 raw payload records forbidden chlorophyll lineage")
    for encoded, expected_variable_count, expected_group_count in zip(
        frame["payload_variables"].astype(str),
        variable_count.astype(int),
        group_count.astype(int),
        strict=True,
    ):
        names = tuple(encoded.split(",")) if encoded else ()
        if len(names) != len(set(names)):
            raise ClosureMIFALRunError("M0 payload_variables contains duplicates")
        canonical_names = tuple(
            variable for variable in STRICT_MIFAL_VARIABLES if variable in names
        )
        if names != canonical_names or len(names) != expected_variable_count:
            raise ClosureMIFALRunError(
                "M0 payload_variables is not the exact ordered payload subsequence"
            )
        derived_groups = sum(
            bool(set(names).intersection(members))
            for members in EVIDENCE_GROUPS.values()
        )
        if derived_groups != expected_group_count:
            raise ClosureMIFALRunError(
                "M0 evidence_group_count disagrees with payload_variables"
            )
    result = frame.sort_values(list(CANONICAL_SORT_COLUMNS), kind="mergesort").reset_index(drop=True)
    if result.duplicated(list(EXACT_KEY_COLUMNS)).any():
        raise ClosureMIFALRunError("M0 raw exact keys are duplicated")
    return result


def raw_arrow_table(frame: pd.DataFrame) -> pa.Table:
    canonical = canonical_m0_raw_frame(frame)
    table = pa.Table.from_pandas(
        canonical,
        schema=RAW_ARROW_SCHEMA,
        preserve_index=False,
        safe=True,
    )
    if table.schema != RAW_ARROW_SCHEMA:
        raise ClosureMIFALRunError("M0 Arrow schema drifted")
    return table


def validate_snapshot_availability(
    raw: pd.DataFrame,
    availability: pd.DataFrame,
) -> dict[str, Any]:
    """Require the frozen 9,732-origin non-Chl evidence distribution."""
    if len(availability) != EXPECTED_INTENT_ORIGINS or availability["common_origin_id"].nunique() != EXPECTED_INTENT_ORIGINS:
        raise ClosureMIFALRunError("M0 origin availability denominator drifted")
    if len(raw) != EXPECTED_COMMON_ROWS or not availability["availability_status"].eq("success").all():
        raise ClosureMIFALRunError("M0 frozen snapshot success denominator drifted")
    group_origins = {
        int(key): int(value)
        for key, value in availability["evidence_group_count"].value_counts().sort_index().items()
    }
    group_rows = {
        int(key): int(value)
        for key, value in raw["evidence_group_count"].value_counts().sort_index().items()
    }
    if group_origins != EXPECTED_GROUP_COUNT_ORIGINS or group_rows != EXPECTED_GROUP_COUNT_ROWS:
        raise ClosureMIFALRunError(
            f"M0 evidence-group distribution drifted: origins={group_origins}, rows={group_rows}"
        )
    variable_coverage = {
        variable: int(availability[f"has_{variable}"].sum())
        for variable in STRICT_MIFAL_VARIABLES
    }
    if variable_coverage != EXPECTED_VARIABLE_COVERAGE:
        raise ClosureMIFALRunError(
            f"M0 variable availability drifted: {variable_coverage}"
        )
    role_origins = {
        str(key): int(value)
        for key, value in availability["time_role"].value_counts().items()
    }
    if role_origins != EXPECTED_ORIGINS_BY_ROLE:
        raise ClosureMIFALRunError(f"M0 role denominators drifted: {role_origins}")
    rows_by_horizon = {
        int(key): int(value)
        for key, value in raw["horizon_months"].value_counts().sort_index().items()
    }
    if rows_by_horizon != {1: EXPECTED_INTENT_ORIGINS, 2: EXPECTED_INTENT_ORIGINS, 3: EXPECTED_INTENT_ORIGINS}:
        raise ClosureMIFALRunError(f"M0 horizon denominators drifted: {rows_by_horizon}")
    return {
        "intent_origins": len(availability),
        "raw_rows": len(raw),
        "eligible_origins": int(availability["availability_status"].eq("success").sum()),
        "input_ineligible_origins": int(availability["availability_status"].ne("success").sum()),
        "origins_by_evidence_group_count": group_origins,
        "rows_by_evidence_group_count": group_rows,
        "origins_by_variable": variable_coverage,
        "origins_by_time_role": role_origins,
        "rows_by_horizon": rows_by_horizon,
    }


def availability_summary(
    raw: pd.DataFrame,
    availability: pd.DataFrame,
) -> pd.DataFrame:
    """Serialize explicit status/group/role/horizon development denominators."""
    rows: list[dict[str, Any]] = []

    def add(dimension: str, value: str, origins: int, raw_rows: int) -> None:
        rows.append(
            {
                "dimension": dimension,
                "value": value,
                "intent_origins": int(origins),
                "raw_rows": int(raw_rows),
            }
        )

    add("overall", "all", availability["common_origin_id"].nunique(), len(raw))
    for status in ("success", "input_ineligible"):
        origin_mask = availability["availability_status"].eq(status)
        row_mask = raw["availability_status"].eq(status)
        add("availability_status", status, origin_mask.sum(), row_mask.sum())
    for group_count in range(5):
        origin_mask = availability["evidence_group_count"].eq(group_count)
        row_mask = raw["evidence_group_count"].eq(group_count)
        add("evidence_group_count", str(group_count), origin_mask.sum(), row_mask.sum())
    for role in ("training", "model_selection", "calibration_threshold"):
        origin_mask = availability["time_role"].eq(role)
        row_mask = raw["time_role"].eq(role)
        add("time_role", role, origin_mask.sum(), row_mask.sum())
    for horizon in HORIZONS:
        row_mask = raw["horizon_months"].eq(horizon)
        add(
            "horizon_months",
            str(horizon),
            raw.loc[row_mask, "common_origin_id"].nunique(),
            row_mask.sum(),
        )
    for variable in STRICT_MIFAL_VARIABLES:
        origins = int(availability[f"has_{variable}"].sum())
        add("payload_variable", variable, origins, origins * len(HORIZONS))
    return pd.DataFrame(rows, columns=["dimension", "value", "intent_origins", "raw_rows"])


def default_config_record() -> dict[str, Any]:
    payload = json.dumps(
        asdict(MIFALConfig()),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    record = {"bytes": len(payload), "sha256": _sha256_bytes(payload)}
    if record != {"bytes": DEFAULT_CONFIG_BYTES, "sha256": DEFAULT_CONFIG_SHA256}:
        raise ClosureMIFALRunError("MIFAL v5 default configuration digest drifted")
    return record


def model_spec_payload(
    source_records: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    config = MIFALConfig()
    sources = {
        str(record["path"]): {
            "bytes": int(record["bytes"]),
            "sha256": str(record["sha256"]),
        }
        for record in source_records
        if str(record.get("path"))
        in {
            RUNNER_SOURCE_PATH.as_posix(),
            ADAPTER_SOURCE_PATH.as_posix(),
            MIFAL_CORE_PATH.as_posix(),
        }
    }
    return {
        "schema_version": "closure_mifal_model_spec_v1",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": MODEL_ID,
        "model_name": "mifal_ed_t2_strict_no_chla_memory",
        "family": "eco_fuzzy_type2",
        "core_version": MIFAL_VERSION,
        "configuration": "unmodified_mifal_v5_ecological_priors",
        "default_config_canonical_json": default_config_record(),
        "source_code": sources,
        "technical_seed": TECHNICAL_SEED,
        "deterministic": True,
        "tuning_performed": False,
        "targets_opened": False,
        "call_policy": {
            "assimilate": False,
            "update_state": False,
            "compute_voi": False,
            "state_carry_between_rows": False,
        },
        "structural_global_priors": {
            "initial_state": list(config.initial_state),
            "gammaM": config.gammaM,
            "memory_fallback": [0.0, 0.35],
            "interpretation": "global_constant_prior_not_observed_chlorophyll_memory",
        },
        "observed_memory_inputs": [],
        "strict_payload_variables": list(STRICT_MIFAL_VARIABLES),
        "legacy_adapter_direct_import_authorized": False,
        "legacy_adapter_invocation_authorized": False,
        "legacy_adapter_data_projection_authorized": False,
        "package_initializer_symbol_loading": "incidental_non_authoritative_no_io",
        "evidence_groups": {name: list(values) for name, values in EVIDENCE_GROUPS.items()},
        "minimum_evidence_groups": MINIMUM_EVIDENCE_GROUPS,
        "score_semantics": SCORE_SEMANTICS,
        "predicted_bloom_probability": None,
        "calibration_status": "not_attempted",
        "execution_device": "cpu",
        "threadpool_limit": 1,
    }


def lineage_audit_payload(
    availability: pd.DataFrame,
    snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    eligible = availability["availability_status"].eq("success")
    minimum_groups = int(availability["evidence_group_count"].min()) if len(availability) else 0
    return {
        "schema_version": "closure_mifal_lineage_audit_v1",
        "experiment_id": "closure_v1",
        "surface_id": SURFACE_ID,
        "model_id": MODEL_ID,
        "status": "passed" if bool(eligible.all()) else "passed_with_retained_input_ineligible_rows",
        "panel_projection_keys": list(PANEL_PROJECTION_COLUMNS[:3]),
        "panel_projection_physical_columns": list(PANEL_PHYSICAL_COLUMNS),
        "panel_projection_physical_column_count": 24,
        "mifal_payload_variables": list(STRICT_MIFAL_VARIABLES),
        "unit_scales": {"Tw": 1.0, "TP": 1.0, "TN": 0.001, "Secchi": 1.0, "Turb": 1.0, "DOb": 1.0},
        "forbidden_exact_columns": sorted(FORBIDDEN_EXACT_COLUMNS),
        "forbidden_columns_read": [],
        "legacy_adapter_direct_import_authorized": False,
        "legacy_adapter_invocation_authorized": False,
        "legacy_adapter_data_projection_authorized": False,
        "package_initializer_symbol_loading": "incidental_non_authoritative_no_io",
        "observed_memory_inputs": [],
        "state_carry_between_rows": False,
        "structural_global_prior": {
            "initial_state": [0.05, 0.35],
            "gammaM": 0.28,
            "memory_fallback": [0.0, 0.35],
            "observed_memory": False,
        },
        "evidence_groups": {name: list(values) for name, values in EVIDENCE_GROUPS.items()},
        "minimum_evidence_groups_required": MINIMUM_EVIDENCE_GROUPS,
        "minimum_evidence_groups_observed": minimum_groups,
        "intent_origins": int(len(availability)),
        "eligible_origins": int(eligible.sum()),
        "input_ineligible_origins": int((~eligible).sum()),
        "origins_by_variable": {
            variable: int(availability[f"has_{variable}"].sum())
            for variable in STRICT_MIFAL_VARIABLES
        },
        "origins_by_evidence_group_count": {
            str(int(key)): int(value)
            for key, value in availability["evidence_group_count"].value_counts().sort_index().items()
        },
        "origins_by_time_role": {
            str(key): int(value)
            for key, value in availability["time_role"].value_counts().items()
        },
        "snapshot_denominators": dict(snapshot or {}),
        "targets_opened": False,
        "outcomes_opened": False,
        "calibration_performed": False,
    }


def _availability_csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, lineterminator="\n").encode("utf-8")


def _report_text(availability: pd.DataFrame) -> str:
    success = int(availability["availability_status"].eq("success").sum())
    unavailable = int(len(availability) - success)
    minimum_groups = int(availability["evidence_group_count"].min()) if len(availability) else 0
    return "\n".join(
        [
            "# Closure V1 M0 development bundle",
            "",
            f"- Model: `{MODEL_ID}` / `mifal_ed_t2_strict_no_chla_memory`",
            f"- Core: MIFAL-ED/T2 `{MIFAL_VERSION}` defaults",
            f"- Intent origins: {len(availability):,}",
            f"- Eligible origins (>=2 ecological groups): {success:,}",
            f"- Retained input-ineligible origins: {unavailable:,}",
            f"- Minimum ecological groups observed: {minimum_groups}",
            f"- Raw prediction rows: {len(availability) * 3:,}",
            "- Observed chlorophyll inputs and memory: absent",
            "- Structural initial state, gammaM, and empty-memory fallback are fixed global priors",
            "- State carry, assimilation, VOI, tuning, targets, calibration, metrics, E0-M, E0-U, DVC, network, and outcomes: not performed",
            "",
        ]
    )


def runtime_version_record() -> dict[str, Any]:
    return {
        "python": platform.python_version(),
        "numpy": distribution_version("numpy"),
        "pandas": distribution_version("pandas"),
        "pyarrow": distribution_version("pyarrow"),
        "threadpoolctl": distribution_version("threadpoolctl"),
        "threadpool_limit": 1,
        "mifal_core": MIFAL_VERSION,
    }


def _execution_input_records(contract: Mapping[str, Any]) -> list[dict[str, Any]]:
    authority = contract.get("authority")
    if not isinstance(authority, Mapping):
        raise ClosureMIFALRunError("M0 runtime authority is missing")
    physical = authority.get("physical_inputs")
    if not isinstance(physical, list) or len(physical) != 23:
        raise ClosureMIFALRunError("M0 must bind exactly 23 physical inputs")
    records: list[dict[str, Any]] = []
    for expected in physical:
        if not isinstance(expected, Mapping):
            raise ClosureMIFALRunError("M0 physical input record is not a mapping")
        logical_path = str(expected.get("path", ""))
        lowered = logical_path.lower()
        if "target" in Path(logical_path).name.lower() or "outcome" in lowered:
            raise ClosureMIFALRunError(
                f"M0 runtime attempts to bind a target/outcome artifact: {logical_path}"
            )
        actual = _file_record(Path(logical_path))
        if (
            actual["bytes"] != expected.get("bytes")
            or actual["sha256"] != expected.get("sha256")
        ):
            raise ClosureMIFALRunError(f"M0 physical input drifted: {logical_path}")
        actual["artifact_role"] = str(expected.get("role", ""))
        records.append(actual)
    for role, path in (
        ("mifal_runtime", RUNTIME_PATH),
        ("effective_patch_lock", PATCH_LOCK_PATH),
        ("effective_patch_lock_manifest", PATCH_COMPANION_PATH),
        ("mifal_development_runner", RUNNER_SOURCE_PATH),
        ("strict_panel_adapter", ADAPTER_SOURCE_PATH),
    ):
        record = _file_record(path)
        record["artifact_role"] = role
        records.append(record)
    if len({record["path"] for record in records}) != len(records):
        raise ClosureMIFALRunError("M0 execution input paths are not unique")
    return records


def _validate_bound_sources(authority: Mapping[str, Any]) -> None:
    expected = {
        RUNTIME_PATH: "runtime_sha256",
        PATCH_LOCK_PATH: "lock_sha256",
        PATCH_COMPANION_PATH: "companion_sha256",
        RUNNER_SOURCE_PATH: "runner_sha256",
        ADAPTER_SOURCE_PATH: "adapter_sha256",
        MIFAL_CORE_PATH: "mifal_core_sha256",
    }
    for path, field in expected.items():
        if _file_record(path)["sha256"] != authority[field]:
            raise ClosureMIFALRunError(f"Effective E0-MR binding drifted: {path}")


def _compare_supplied_authority(
    supplied: Mapping[str, Any] | None,
    effective: Mapping[str, Any],
) -> None:
    if supplied is not None and dict(supplied) != dict(effective):
        raise ClosureMIFALRunError(
            "Supplied E0-MR authority differs from the effective published authority"
        )


def preflight(authority: Mapping[str, Any] | None = None) -> dict[str, Any]:
    effective = _require_effective_authority()
    _compare_supplied_authority(authority, effective)
    return _preflight_with_verified_authority(effective)


def _preflight_with_verified_authority(authority: Mapping[str, Any]) -> dict[str, Any]:
    contract = load_runtime_contract()
    snapshot = _validated_authority_snapshot(authority)
    _assert_absent_namespace()
    _validate_bound_sources(snapshot)
    return {
        "status": "ready_to_execute_one_shot",
        "gate": "E0-MR",
        "mifal_one_shot_authorized": True,
        "common_origin_rows": EXPECTED_COMMON_ROWS,
        "intent_origins": EXPECTED_INTENT_ORIGINS,
        "technical_seed": TECHNICAL_SEED,
        "raw_column_count": len(RAW_PREDICTION_COLUMNS),
        "expected_final_path_count": len(EXPECTED_OUTPUT_PATHS),
        "authority_binding": snapshot,
        "runtime_schema_version": contract["schema_version"],
        "writes_performed": False,
        "target_paths_opened": False,
        "outcome_paths_opened": False,
        "dvc_commands_run": False,
        "network_calls_made": False,
    }


def execute_one_shot(authority: Mapping[str, Any] | None = None) -> dict[str, Any]:
    effective = _require_effective_authority()
    _compare_supplied_authority(authority, effective)
    return _execute_one_shot_with_verified_authority(effective)


def _execute_one_shot_with_verified_authority(
    effective_authority: Mapping[str, Any],
) -> dict[str, Any]:
    contract = load_runtime_contract()
    preflight_result = _preflight_with_verified_authority(effective_authority)
    snapshot = _validated_authority_snapshot(effective_authority)
    guard = _acquire_guard()
    guard_active = True
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        _assert_absent_namespace(allow_guard=True)
        input_records_before = _execution_input_records(contract)
        gate = load_development_gate()
        common = _load_common_frame()
        assert_development_frame(common, gate, role_column="time_role")
        development_site_ids = sorted(site for source, site in gate.development_keys if source == "wqp")
        if len(development_site_ids) != EXPECTED_DEVELOPMENT_LOCATIONS:
            raise ClosureMIFALRunError("Development-location denominator drifted")
        panel = _load_panel_frame(development_site_ids)
        with threadpool_limits(limits=1):
            raw, availability = build_m0_predictions(common, panel)
            table = raw_arrow_table(raw)
        if len(raw) != EXPECTED_COMMON_ROWS or len(availability) != EXPECTED_INTENT_ORIGINS:
            raise ClosureMIFALRunError("M0 output denominator drifted")
        snapshot_denominators = validate_snapshot_availability(raw, availability)
        availability_output = availability_summary(raw, availability)
        input_records_after = _execution_input_records(contract)
        if input_records_before != input_records_after:
            raise ClosureMIFALRunError("M0 inputs changed during one-shot execution")
        spec = model_spec_payload(input_records_after)
        lineage = lineage_audit_payload(availability, snapshot_denominators)
        _assert_absent_namespace(allow_guard=True)
        with OutputTransaction() as transaction:
            output_records: list[dict[str, Any]] = []
            raw_owned = transaction.publish_arrow_table(table, RAW_OUTPUT_PATH)
            output_records.append(transaction.file_record(raw_owned, logical_path=RAW_OUTPUT_PATH))
            for payload, path in ((spec, MODEL_SPEC_PATH), (lineage, LINEAGE_AUDIT_PATH)):
                owned = transaction.publish_bytes(_canonical_json_bytes(payload), path)
                output_records.append(transaction.file_record(owned, logical_path=path))
            availability_owned = transaction.publish_bytes(
                _availability_csv_bytes(availability_output),
                AVAILABILITY_PATH,
            )
            output_records.append(
                transaction.file_record(availability_owned, logical_path=AVAILABILITY_PATH)
            )
            report_owned = transaction.publish_bytes(_report_text(availability).encode("utf-8"), REPORT_PATH)
            output_records.append(transaction.file_record(report_owned, logical_path=REPORT_PATH))
            manifest_payload = {
                "schema_version": "closure_mifal_development_manifest_v1",
                "experiment_id": "closure_v1",
                "surface_id": SURFACE_ID,
                "model_id": MODEL_ID,
                "gate": "E0-MR",
                "status": "mifal_development_bundle_written_unpublished",
                "started_at_utc": started_at,
                "counts": {
                    "raw_rows": len(raw),
                    "intent_origins": len(availability),
                    "eligible_origins": int(availability["availability_status"].eq("success").sum()),
                    "input_ineligible_origins": int(availability["availability_status"].ne("success").sum()),
                    "development_locations": EXPECTED_DEVELOPMENT_LOCATIONS,
                    "final_paths": len(EXPECTED_OUTPUT_PATHS),
                },
                "raw_prediction_contract": raw_prediction_contract(),
                "model_spec_sha256": _sha256_bytes(_canonical_json_bytes(spec)),
                "lineage_audit_sha256": _sha256_bytes(_canonical_json_bytes(lineage)),
                "runtime_versions": runtime_version_record(),
                "effective_authority": snapshot,
                "inputs": input_records_after,
                "script": next(
                    dict(record)
                    for record in input_records_after
                    if record["path"] == RUNNER_SOURCE_PATH.as_posix()
                ),
                "source_code": [
                    dict(record)
                    for record in input_records_after
                    if record["path"]
                    in {
                        RUNNER_SOURCE_PATH.as_posix(),
                        ADAPTER_SOURCE_PATH.as_posix(),
                        MIFAL_CORE_PATH.as_posix(),
                    }
                ],
                "outputs": output_records,
                "manifest_written_last": True,
                "tuning_performed": False,
                "targets_opened": False,
                "calibration_performed": False,
                "metrics_computed": False,
                "e0_m_authorized": False,
                "evaluation_authorized": False,
                "e0_u_authorized": False,
                "dvc_commands_run": False,
                "network_calls_made": False,
                "future_outcomes_accessed": False,
                "outcome_access_log_state": "absent",
                "completion_marker_written_last": True,
            }
            manifest_owned = transaction.publish_bytes(
                _manifest_json_bytes(manifest_payload),
                MANIFEST_PATH,
            )
            manifest_record = transaction.file_record(
                manifest_owned,
                logical_path=MANIFEST_PATH,
            )
            _assert_no_forbidden_side_effects()
            _assert_exact_published_namespace()
            try:
                _release_guard(guard)
            finally:
                # A release failure must still unwind through OutputTransaction
                # so every owned final is rolled back.
                guard_active = False
        return {
            **preflight_result,
            "status": "mifal_development_bundle_written_unpublished",
            "writes_performed": True,
            "raw_rows": len(raw),
            "intent_origins": len(availability),
            "eligible_origins": int(availability["availability_status"].eq("success").sum()),
            "manifest": manifest_record,
            "target_paths_opened": False,
            "outcome_paths_opened": False,
            "dvc_commands_run": False,
            "network_calls_made": False,
        }
    except BaseException as exc:
        if guard_active:
            guard_active = False
            try:
                _release_guard(guard)
            except ClosureMIFALRunError as cleanup_error:
                raise cleanup_error from exc
        raise


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check-only", action="store_true")
    modes.add_argument("--execute-one-shot", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    # The effective authority is the first operation after argument parsing.
    authority = _require_effective_authority()
    result = (
        _preflight_with_verified_authority(authority)
        if args.check_only
        else _execute_one_shot_with_verified_authority(authority)
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
