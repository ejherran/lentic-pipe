#!/usr/bin/env python
"""Validate the additive Closure V1 E0-DLP development-runtime patch lock.

E0-DLP is deliberately additive.  It preserves the published E0-DL bytes and
the already completed ANFIS seed-1729 bundle, while locking a narrowly scoped
compatibility correction before any additional development fit.  This module
never reads scientific outcomes and never authorizes evaluation or E0-U.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import re
import stat
import subprocess
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import yaml

from src.experiments.closure_contract import (
    ClosureContractError,
    load_json_mapping,
    load_yaml_mapping,
    validate_json_schema,
)
from src.experiments.closure_development_guard import (
    DEVELOPMENT_ROLES,
    assert_development_frame,
    load_development_gate,
)
from src.experiments.closure_development_runtime_lock import (
    DEFAULT_LOCK_PATH,
    DEFAULT_LOCK_SCHEMA,
    DEFAULT_RUNTIME_CONFIG,
    DEFAULT_RUNTIME_SCHEMA,
    EXPECTED_AUTHORIZATIONS as BASE_AUTHORIZATIONS,
    EXPECTED_CANONICAL_ORIGIN_IDENTITY_SHA256,
    EXPECTED_PATH_COUNT,
    EXPECTED_PATH_DIGEST,
    EXPECTED_RUNTIME_STATUS,
    EXPECTED_SEALS as BASE_SEALS,
    LOCK_VERSION as BASE_LOCK_VERSION,
    TYPE_CHECK_COMMAND,
    _locked_artifact_matches_observed_metadata,
    _dvc_remote_configuration_fingerprint,
    _dvc_remote_name,
    _require_exact_record_set,
    _runtime_paths_match_contract,
    _validate_parent_lock_metadata,
    _validate_restored_source_lock_metadata,
    _validate_runtime_prelock_contract,
    canonical_origin_identity,
    common_origin_lock_record,
    environment_payload,
    expert_state_lock_record,
    focused_test_command,
    parent_records,
    planned_artifact_records,
    restored_development_source_records,
    validate_development_runtime_lock_payload,
    validate_dvc_remote_verification_evidence,
)
from src.experiments.closure_runtime_contract import closure_state_deltas


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PATCH_LOCK_VERSION = "closure_development_runtime_patch_lock_v1_1"
DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/development_runtime_patch_lock.json"
)
DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/development_runtime_patch_lock.schema.json"
)

PATCH_GATE = "E0-DLP"
PATCH_ID = "development_runtime_compatibility_patch_1"
PATCH_STATUS = "locked"
EXPERIMENT_ID = "closure_v1"
ADOPTED_BASE_SEED = 1729
EXPECTED_PUBLISHED_REF = "origin/main"
REJECTED_SYNTHETIC_REF = "refs/remotes/origin/main"
EXPECTED_BASE_LOCK_COMMIT = "e7becdd5553decc92bbcf0af4cede7425ed12546"
EXPECTED_BASE_LOCKED_HEAD = "4fe2d02a0abf4e044e5f2aa223c99ccc95ee7cd3"
EXPECTED_ADOPTION_HEAD = "e8fa8b8e8ca26e3457bd073934c158c1d8ee15bf"
EXPECTED_ACTIVATION_HEAD = "350c6b61c497384f5db7fee99e731c02d521e33d"
EXPECTED_BASE_LOCK_BYTES = 95_285
EXPECTED_BASE_LOCK_SHA256 = (
    "5d858028ff5df561cc4a5e6086d9f83d08ac4c5ef6ffe27e844001f9fa495a81"
)
EXPECTED_BASE_MODELS_OWNER_MD5 = "458e4ebf186f91dba8608f951b998483.dir"
EXPECTED_BASE_MODELS_OWNER_SIZE = 115_691_694
EXPECTED_BASE_MODELS_OWNER_NFILES = 173
EXPECTED_BASE_MODELS_TREE_BYTES = 24_671
EXPECTED_BASE_MODELS_TREE_SHA256 = (
    "cf642de4acbf4b42a33415774a0603a30f5b8abe52553c073a5bf5139ebc6569"
)
EXPECTED_ADOPTED_MODELS_OWNER_SIZE = 115_709_141
EXPECTED_ADOPTED_MODELS_OWNER_NFILES = 176
EXPECTED_ADOPTED_MODELS_OWNER_MD5 = "70cfb056dcd1789cf41d54cd5e7ae90c.dir"
EXPECTED_SEED_STATE_MD5 = "183bc5e98b1d5fa5084300ded6476712"

FITTED_MODULE_METRIC_COLUMNS = (
    "module",
    "status",
    "base_seed",
    "module_seed",
    "train_rows",
    "prediction_rows",
    "input_dimension",
    "rule_count",
    "epochs",
    "curve_initial_pre_update_loss",
    "curve_last_pre_update_loss",
    "minimum_curve_pre_update_loss",
    "final_checkpoint_loss",
    "quality_gate_output_standard_deviation",
    "quality_gate_output_scope",
    "materialized_surface_output_standard_deviation",
    "maximum_parameter_delta",
    "centers_ordered",
    "centers_in_unit_interval",
)
UNAVAILABLE_MODULE_METRIC_COLUMNS = (
    "module",
    "status",
    "failure_reason",
    "base_seed",
    "module_seed",
    "input_rows",
    "excluded_nonfinite_target_rows",
    "excluded_missingness_rows",
    "eligible_universe_rows",
    "selected_rows",
    "required_rows",
    "replacement_used",
    "fit_attempted",
)

BASE_COMPONENT_DRIFT_ALLOWLIST = (
    "src/experiments/build_closure_pipe_sequences.py",
    "src/experiments/closure_development_runtime_lock.py",
    "src/experiments/fit_closure_anfis_state.py",
    "tests/test_build_closure_pipe_sequences.py",
    "tests/test_closure_development_runtime_lock.py",
    "tests/test_fit_closure_anfis_state.py",
)
PATCH_ACTIVATION_PATHS = (
    "src/experiments/closure_development_runtime_lock.py",
    "src/experiments/fit_closure_anfis_state.py",
    "tests/test_closure_development_runtime_lock.py",
    "tests/test_fit_closure_anfis_state.py",
)
PATCH_REPAIR_PATHS = (
    "configs/closure_v1/development_runtime_patch_lock.schema.json",
    "docs/closure_v1/E0_D_RUNTIME_PATCH_1.md",
    "src/experiments/closure_development_runtime_patch.py",
    "tests/test_closure_development_runtime_patch.py",
)

PATCH_COMPONENT_ROLES = {
    "configs/closure_v1/development_runtime_patch_lock.schema.json": (
        "development_runtime_patch_lock_schema"
    ),
    "src/experiments/closure_development_runtime_patch.py": (
        "development_runtime_patch_validator"
    ),
    "src/experiments/lock_closure_development_runtime_patch.py": (
        "development_runtime_patch_locker"
    ),
    "tests/test_closure_development_runtime_patch.py": (
        "development_runtime_patch_tests"
    ),
    "docs/closure_v1/E0_D_RUNTIME_PATCH_1.md": (
        "development_runtime_patch_protocol"
    ),
}

DEFAULT_PATCH_LOCK_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/development_runtime_patch_lock_manifest.json"
)

SEED_MANIFEST_PATH = Path(
    "reports/closure_v1/01_surface/anfis/seed_1729/manifest.json"
)
SEED_STATE_PATH = Path(
    "data/closure_v1/development/anfis/seed_1729/adaptive_no_current_state.parquet"
)
SEED_STATE_POINTER_PATH = Path(f"{SEED_STATE_PATH.as_posix()}.dvc")
MODELS_OWNER_PATH = Path("models.dvc")
SEED_CHECKPOINT_PATHS = (
    Path("models/closure_v1/anfis/seed_1729/ANFIS-N.pt"),
    Path("models/closure_v1/anfis/seed_1729/ANFIS-F.pt"),
    Path("models/closure_v1/anfis/seed_1729/ANFIS-T-no-current.pt"),
)
SEED_CHECKPOINT_MD5 = {
    SEED_CHECKPOINT_PATHS[0].as_posix(): "9485f2a183c8509255ebb8b9e9606517",
    SEED_CHECKPOINT_PATHS[1].as_posix(): "6a916f6077406ff7bbe7e25afd773d84",
    SEED_CHECKPOINT_PATHS[2].as_posix(): "e376b6f9e3ff929da440e937e70f95f0",
}
HISTORICAL_RUNTIME_VALIDATOR_RECORD = {
    "path": "src/experiments/closure_development_runtime_lock.py",
    "role": "runtime_lock_validator",
    "bytes": 121_036,
    "sha256": "024b942d32db1dc65500fac9ff9b56be9e983307ce6427dbb4f7fac966e78000",
}
HISTORICAL_ANFIS_FITTER_FILE = {
    "path": "src/experiments/fit_closure_anfis_state.py",
    "bytes": 59_865,
    "sha256": "8177a9e19943222e51b16befc6f05e3978faa8abd46d37b7f43fa724fbd454f2",
}
HISTORICAL_ANFIS_SCRIPT_RECORD = {
    **HISTORICAL_ANFIS_FITTER_FILE,
    "role": "generating_script",
}
HISTORICAL_ANFIS_DEPENDENCY_RECORD = {
    **HISTORICAL_ANFIS_FITTER_FILE,
    "role": "strict_anfis_state_adapter",
}
HISTORICAL_ANFIS_TEST_RECORD = {
    "path": "tests/test_fit_closure_anfis_state.py",
    "role": "producer_completion_order_regression",
    "bytes": 37_021,
    "sha256": "1022b4a1915e787fc92dae011d4d04a0a53f4dae784e64bdc442a9f906f212b6",
}
SEED_LIGHTWEIGHT_PATHS = (
    Path("reports/closure_v1/01_surface/anfis/seed_1729/ANFIS-N_sample_keys.csv"),
    Path("reports/closure_v1/01_surface/anfis/seed_1729/ANFIS-F_sample_keys.csv"),
    Path(
        "reports/closure_v1/01_surface/anfis/seed_1729/"
        "ANFIS-T-no-current_sample_keys.csv"
    ),
    Path("reports/closure_v1/01_surface/anfis/seed_1729/module_metrics.csv"),
    Path("reports/closure_v1/01_surface/anfis/seed_1729/training_curve.csv"),
    Path("reports/closure_v1/01_surface/anfis/seed_1729/memberships_initial.csv"),
    Path("reports/closure_v1/01_surface/anfis/seed_1729/memberships_final.csv"),
    Path("reports/closure_v1/01_surface/anfis/seed_1729/report.md"),
    Path("reports/closure_v1/01_surface/anfis/seed_1729/lineage_audit.json"),
)

EXPECTED_SEED_FINALS: dict[str, tuple[int, str]] = {
    SEED_MANIFEST_PATH.as_posix(): (
        20_768,
        "b38e54d21dd64edbf5a5968d9bee505569ea72b9f03c6750baf9a54114e9ef82",
    ),
    SEED_STATE_PATH.as_posix(): (
        1_215_081,
        "c1987e31edb5b0f830f433120715f2abb7d7a375f8f38e6ad24056fc12447c69",
    ),
    SEED_CHECKPOINT_PATHS[0].as_posix(): (
        5_050,
        "cbf3ec20445b0cdb0b4915bb3b5fcff3a293688cdf605fb1d4300728341b61d6",
    ),
    SEED_CHECKPOINT_PATHS[1].as_posix(): (
        8_250,
        "741d3ab0b9980c1f4c61447b1d9150bdd24ba649ab7c7057181c7c825c7bcfc6",
    ),
    SEED_CHECKPOINT_PATHS[2].as_posix(): (
        4_147,
        "45064d6b3bffe102a4d4d6689f0bc0709791cd5df5b328323f96e7c3b507e6a8",
    ),
    SEED_LIGHTWEIGHT_PATHS[0].as_posix(): (
        463_207,
        "754a8b8c29bdd40145f859983da64f3287ae8c527a413e0b9e8d68bb83a92b8c",
    ),
    SEED_LIGHTWEIGHT_PATHS[1].as_posix(): (
        458_422,
        "f15beef010139fcb8c5ef5f729d41e3de0a67492c87982f0f8a8a0838375ac72",
    ),
    SEED_LIGHTWEIGHT_PATHS[2].as_posix(): (
        503_037,
        "5b31f6b032df20b3e5a5a1d5fa2ba4b0beeeb174284ff5229b30bfe570a91114",
    ),
    SEED_LIGHTWEIGHT_PATHS[3].as_posix(): (
        1_104,
        "85ae8a11f52edf9c9cf927595782a64eff74ab76f1b58f4324095bd9ef274e22",
    ),
    SEED_LIGHTWEIGHT_PATHS[4].as_posix(): (
        7_673,
        "bace68b15b08ce460d124f113961e827d4e415863933192a2b23c632fb372af8",
    ),
    SEED_LIGHTWEIGHT_PATHS[5].as_posix(): (
        1_293,
        "cf49de8f2aa49679baeaad9d856acc6384c76f9f31d6e4fff3436f8ec6c46467",
    ),
    SEED_LIGHTWEIGHT_PATHS[6].as_posix(): (
        1_719,
        "f6d0fbcf7f04743a59a804162fb252f429e2bfe2bc4272bf27924490c7aff1bd",
    ),
    SEED_LIGHTWEIGHT_PATHS[7].as_posix(): (
        444,
        "feb6e21a63d73cdf1312159ab0fdde7bd46b8fa1eb8e4cf9d32c9e487822aeae",
    ),
    SEED_LIGHTWEIGHT_PATHS[8].as_posix(): (
        2_863,
        "f54c8a5cdc15de8b31dd8337fda3ac1025ef500c7ad935811a643e4216e8a894",
    ),
}

EXPECTED_SEED_OUTPUT_METADATA: dict[str, dict[str, str]] = {
    SEED_STATE_PATH.as_posix(): {"role": "adaptive_no_current_state"},
    SEED_CHECKPOINT_PATHS[0].as_posix(): {
        "role": "anfis_checkpoint",
        "module": "ANFIS-N",
    },
    SEED_CHECKPOINT_PATHS[1].as_posix(): {
        "role": "anfis_checkpoint",
        "module": "ANFIS-F",
    },
    SEED_CHECKPOINT_PATHS[2].as_posix(): {
        "role": "anfis_checkpoint",
        "module": "ANFIS-T-no-current",
    },
    SEED_LIGHTWEIGHT_PATHS[0].as_posix(): {
        "role": "sample_keys",
        "module": "ANFIS-N",
    },
    SEED_LIGHTWEIGHT_PATHS[1].as_posix(): {
        "role": "sample_keys",
        "module": "ANFIS-F",
    },
    SEED_LIGHTWEIGHT_PATHS[2].as_posix(): {
        "role": "sample_keys",
        "module": "ANFIS-T-no-current",
    },
    SEED_LIGHTWEIGHT_PATHS[3].as_posix(): {"role": "module_metrics"},
    SEED_LIGHTWEIGHT_PATHS[4].as_posix(): {"role": "training_curve"},
    SEED_LIGHTWEIGHT_PATHS[5].as_posix(): {"role": "memberships_initial"},
    SEED_LIGHTWEIGHT_PATHS[6].as_posix(): {"role": "memberships_final"},
    SEED_LIGHTWEIGHT_PATHS[7].as_posix(): {"role": "report"},
    SEED_LIGHTWEIGHT_PATHS[8].as_posix(): {"role": "lineage_audit"},
}

PATCH_PARENT_DIFF_ALLOWLIST = tuple(
    sorted(
        {
            *BASE_COMPONENT_DRIFT_ALLOWLIST,
            *PATCH_COMPONENT_ROLES,
            SEED_MANIFEST_PATH.as_posix(),
            *(path.as_posix() for path in SEED_LIGHTWEIGHT_PATHS),
            SEED_STATE_POINTER_PATH.as_posix(),
            MODELS_OWNER_PATH.as_posix(),
        }
    )
)
PATCH_ADOPTION_DIFF_ALLOWLIST = tuple(
    path for path in PATCH_PARENT_DIFF_ALLOWLIST if path not in PATCH_ACTIVATION_PATHS
)

PATCH_FOCUSED_TEST_COMMAND = (
    ".venv/bin/pytest",
    "tests/test_closure_development_runtime_patch.py",
    "tests/test_build_closure_pipe_sequences.py",
    "tests/test_closure_development_runtime_lock.py",
    "tests/test_fit_closure_anfis_state.py",
    "-q",
)
PATCH_TYPE_CHECK_COMMAND = (".venv/bin/ty", "check")
PATCH_FOCUSED_TEST_COUNT = 231
PATCH_TEST_ENVIRONMENT = {
    "PYTEST_ADDOPTS": "",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    "PYTEST_PLUGINS": "",
    "PY_COLORS": "0",
}
DVC_REMOTE_VERIFICATION_METHOD = "two_targeted_idempotent_pushes_v1"
DVC_REMOTE_ENVIRONMENT = {"LC_ALL": "C", "LANG": "C", "DVC_NO_ANALYTICS": "1"}
DVC_EXECUTABLE = ".venv/bin/dvc"

PATCH_AUTHORIZATIONS = {
    "development_fit_authorized": True,
    "evaluation_authorized": False,
    "e0_u_authorized": False,
}
PATCH_SEALS = {
    "future_outcomes_accessed": False,
    "post_2021_outcome_semantic_decode": False,
    "lock_generation_reads_scientific_outcome_rows": False,
    "lock_generation_reads_post_2021_outcomes": False,
    "scientific_runtime_contract_changed": False,
    "base_e0_dl_replaced": False,
    "original_seed_manifest_mutated": False,
    "original_seed_rematerialized": False,
    "does_not_replace_e0_m_model_lock": True,
}
PATCH_AUDITS = {
    "base_lock_preserved": True,
    "base_records_verified_at_locked_h": True,
    "base_physical_authority_verified": True,
    "base_lock_publication_verified": True,
    "patch_parent_published": True,
    "ancestry_verified": True,
    "published_head_is_ancestor_of_execution": True,
    "diff_allowlist_verified": True,
    "exact_base_component_drift_verified": True,
    "patch_components_verified": True,
    "patch_records_verified_at_execution_head": True,
    "patch_lock_artifact_verified": True,
    "three_runtime_compatibility_corrections_verified": True,
    "seed_1729_bundle_verified": True,
    "content_addressed_completion_order_evidence_verified": True,
    "seed_1729_preserved_without_rematerialization": True,
    "dvc_ownership_verified": True,
    "dvc_remote_verified_at_patch": True,
    "zero_holdout_overlap": True,
    "zero_unknown_assignment_overlap": True,
    "no_post_2021_materialization": True,
    "environment_locked": True,
    "legacy_summary_shape_verified": True,
}
PATCH_IMPLEMENTATION_ERRATUM = {
    "erratum_id": "dvc_mtime_nonportable_completion_evidence_1",
    "classification": "reproducibility_evidence_correction_only",
    "trigger": "dvc_hardlink_materialization_mtime_postdates_producer_manifest",
    "superseded_evidence": "workspace_filesystem_mtime_order_v1",
    "replacement_evidence": (
        "git_locked_producer_control_flow_and_content_addressed_bundle_v1"
    ),
    "filesystem_mtime_used": False,
    "erratum_changes_seed_artifact_bytes": False,
    "erratum_changes_seed_artifact_timestamps": False,
    "git_history_rewritten": False,
    "scientific_runtime_contract_changed": False,
    "outcome_access_changed": False,
}

STATE_ALLOWLIST = (
    "source_id",
    "site_id",
    "year_month",
    "time_role",
    "yN_adaptive",
    "yF_adaptive",
    "yT_no_chla_adaptive",
    "sigma_N_adaptive",
    "sigma_F_adaptive",
    "sigma_T_no_chla_adaptive",
    "delta_yN_adaptive",
    "delta_yF_adaptive",
    "delta_yT_no_chla_adaptive",
    "delta_previous_month_missing",
)
LEVEL_COLUMNS = (
    "yN_adaptive",
    "yF_adaptive",
    "yT_no_chla_adaptive",
    "sigma_N_adaptive",
    "sigma_F_adaptive",
    "sigma_T_no_chla_adaptive",
)
DELTA_COLUMNS = (
    "delta_yN_adaptive",
    "delta_yF_adaptive",
    "delta_yT_no_chla_adaptive",
)
MODULES = ("ANFIS-N", "ANFIS-F", "ANFIS-T-no-current")
MODULE_SEEDS = {"ANFIS-N": 1830, "ANFIS-F": 1931, "ANFIS-T-no-current": 2133}
MODULE_FEATURES = {
    "ANFIS-N": ("tp_pressure", "tn_pressure", "ratio_imbalance_pressure"),
    "ANFIS-F": ("do_good", "ph_good", "turbidity_good", "secchi_good"),
    "ANFIS-T-no-current": ("temp_favorable",),
}
MODULE_TARGETS = {
    "ANFIS-N": "yN",
    "ANFIS-F": "yF",
    "ANFIS-T-no-current": "yT_no_chla",
}
MODULE_ARTIFACT_TOKENS = {
    "ANFIS-N": "anfis_n",
    "ANFIS-F": "anfis_f",
    "ANFIS-T-no-current": "anfis_t_no_current",
}

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
MD5_RE = re.compile(r"^[0-9a-f]{32}$")
DIR_MD5_RE = re.compile(r"^[0-9a-f]{32}\.dir$")

LEGACY_SUMMARY_KEYS = frozenset(
    {
        "lock_path",
        "lock_sha256",
        "lock_version",
        "status",
        "locked_repository_head",
        "execution_head",
        "published_ref",
        "published_head",
        "remote_main_oid",
        "locked_head_is_ancestor",
        "locked_parent_published_at_lock",
        "publication_verified",
        "tracking_ref_publication_verified",
        "remote_publication_verified",
        "canonical_origin_identity_verified",
        "component_count",
        "planned_artifact_path_count",
        "planned_artifact_paths_sha256",
        "device",
        "metadata_verified",
        "physical_artifacts_required",
        "physical_artifacts_verified",
        "common_origin_output_verified",
        "expert_state_output_verified",
        "restored_development_sources_verified",
        "dvc_remote_verified_at_lock",
        "dvc_remote_verified",
        "fit_authorization_predicates",
        "payload_development_fit_authorized",
        "payload_evaluation_authorized",
        "payload_e0_u_authorized",
        "development_fit_authorized",
        "evaluation_authorized",
        "e0_u_authorized",
        "fit_authorized",
        "future_outcomes_accessed",
    }
)


class DevelopmentRuntimePatchError(ClosureContractError):
    """Raised when the additive E0-DLP authority or adopted seed drifts."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _md5_file(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve(path: str | Path) -> Path:
    logical = Path(path)
    candidate = logical if logical.is_absolute() else PROJECT_ROOT / logical
    resolved = candidate.resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise DevelopmentRuntimePatchError(f"Path escapes repository: {path}") from exc
    return resolved


def _lexical_repository_path(path: str | Path) -> Path:
    logical = Path(path)
    candidate = logical if logical.is_absolute() else PROJECT_ROOT / logical
    lexical = Path(os.path.abspath(candidate))
    try:
        lexical.relative_to(PROJECT_ROOT.resolve())
        lexical.parent.resolve(strict=True).relative_to(PROJECT_ROOT.resolve())
    except (FileNotFoundError, ValueError) as exc:
        raise DevelopmentRuntimePatchError(f"Path escapes repository: {path}") from exc
    return lexical


def _relative(path: str | Path) -> str:
    return _lexical_repository_path(path).relative_to(PROJECT_ROOT.resolve()).as_posix()


def _require_default_validation_paths(
    *,
    patch_lock_path: Path,
    patch_lock_schema: Path,
    base_lock_path: Path,
    base_lock_schema: Path,
    runtime_config: Path,
    runtime_schema: Path,
) -> None:
    pairs = (
        (_relative(patch_lock_path), DEFAULT_PATCH_LOCK_PATH.as_posix()),
        (_relative(patch_lock_schema), DEFAULT_PATCH_LOCK_SCHEMA.as_posix()),
        (_relative(base_lock_path), DEFAULT_LOCK_PATH.as_posix()),
        (_relative(base_lock_schema), DEFAULT_LOCK_SCHEMA.as_posix()),
        (_relative(runtime_config), DEFAULT_RUNTIME_CONFIG.as_posix()),
        (_relative(runtime_schema), DEFAULT_RUNTIME_SCHEMA.as_posix()),
    )
    drifted = [
        {"observed": observed, "required": required}
        for observed, required in pairs
        if observed != required
    ]
    if drifted:
        raise DevelopmentRuntimePatchError(
            f"E0-DLP validation requires the closed default paths: {drifted}"
        )


def _file_record(path: str | Path, *, role: str) -> dict[str, Any]:
    resolved = _lexical_repository_path(path)
    try:
        before = resolved.lstat()
    except FileNotFoundError as exc:
        raise DevelopmentRuntimePatchError(
            f"Required E0-DLP file is missing: {_relative(path)}"
        ) from exc
    if not stat.S_ISREG(before.st_mode):
        raise DevelopmentRuntimePatchError(
            f"Required E0-DLP path is not a regular file: {_relative(path)}"
        )
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(resolved, flags)
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise DevelopmentRuntimePatchError(
                f"Required E0-DLP file changed before reading: {_relative(path)}"
            )
        digest = hashlib.sha256()
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
        sha256 = digest.hexdigest()
    finally:
        os.close(descriptor)
    after = resolved.lstat()
    if (before.st_dev, before.st_ino, before.st_size) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
    ):
        raise DevelopmentRuntimePatchError(
            f"Required E0-DLP file changed while reading: {_relative(path)}"
        )
    return {
        "path": _relative(path),
        "role": role,
        "bytes": before.st_size,
        "sha256": sha256,
    }


def _read_regular_repository_bytes(path: str | Path, *, context: str) -> bytes:
    lexical = _lexical_repository_path(path)
    try:
        before = lexical.lstat()
    except FileNotFoundError as exc:
        raise DevelopmentRuntimePatchError(f"{context} is absent: {_relative(path)}") from exc
    if not stat.S_ISREG(before.st_mode):
        raise DevelopmentRuntimePatchError(
            f"{context} is not a regular file: {_relative(path)}"
        )
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(lexical, flags)
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise DevelopmentRuntimePatchError(f"{context} changed before reading")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
    finally:
        os.close(descriptor)
    after = lexical.lstat()
    if (before.st_dev, before.st_ino, before.st_size) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
    ):
        raise DevelopmentRuntimePatchError(f"{context} changed while reading")
    return b"".join(chunks)


def _decode_json_mapping_bytes(raw: bytes, *, context: str) -> dict[str, Any]:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        mapping: dict[str, Any] = {}
        for key, value in pairs:
            if key in mapping:
                raise DevelopmentRuntimePatchError(
                    f"{context} contains duplicate JSON key: {key}"
                )
            mapping[key] = value
        return mapping

    try:
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DevelopmentRuntimePatchError(f"{context} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise DevelopmentRuntimePatchError(f"{context} must be a JSON object")
    return payload


def _load_regular_json_mapping(path: str | Path, *, context: str) -> dict[str, Any]:
    raw = _read_regular_repository_bytes(path, context=context)
    return _decode_json_mapping_bytes(raw, context=context)


def _record_digest(records: Sequence[Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in records:
        encoded = json.dumps(
            dict(record), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        digest.update(encoded)
        digest.update(b"\n")
    return digest.hexdigest()


def _dvc_tree_bytes(entries: Sequence[Mapping[str, Any]]) -> bytes:
    """Render the canonical DVC directory-object JSON representation."""
    return json.dumps(
        [dict(entry) for entry in entries],
        ensure_ascii=True,
        sort_keys=True,
    ).encode("utf-8")


def _path_digest(paths: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise DevelopmentRuntimePatchError(
            f"Git command failed ({' '.join(args)}): {result.stderr.strip()}"
        )
    return result.stdout.strip()


def _git_blob(head: str, path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{head}:{path}"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
    )
    return result.stdout if result.returncode == 0 else None


def _require_commit(value: Any, *, context: str) -> str:
    if not isinstance(value, str) or SHA1_RE.fullmatch(value) is None:
        raise DevelopmentRuntimePatchError(f"{context} must be a full Git commit ID")
    return value


def _require_ancestor(ancestor: str, descendant: str) -> None:
    _require_commit(ancestor, context="ancestor")
    _require_commit(descendant, context="descendant")
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        raise DevelopmentRuntimePatchError(
            f"Required Git ancestry is absent: {ancestor} !<= {descendant}"
        )


def _introduced_commit(path: str | Path) -> str:
    relative = _relative(path)
    commits = [
        value
        for value in _git("log", "--diff-filter=A", "--format=%H", "--", relative).splitlines()
        if value
    ]
    if len(commits) != 1 or SHA1_RE.fullmatch(commits[0]) is None:
        raise DevelopmentRuntimePatchError(
            f"Cannot resolve one immutable introduction commit for {relative}"
        )
    return commits[0]


def _repository_state() -> dict[str, Any]:
    status = _git("status", "--porcelain", "--untracked-files=all")
    return {
        "head": _git("rev-parse", "HEAD"),
        "branch": _git("branch", "--show-current") or "detached",
        "worktree_status": "clean" if not status else "dirty",
        "dirty_paths": status.splitlines(),
    }


def _require_clean_repository() -> dict[str, Any]:
    state = _repository_state()
    if state["worktree_status"] != "clean" or state["dirty_paths"] != []:
        raise DevelopmentRuntimePatchError(
            "E0-DLP generation requires a fully clean committed patch parent"
        )
    _require_commit(state["head"], context="patch parent HEAD")
    if state["branch"] != "main":
        raise DevelopmentRuntimePatchError("E0-DLP patch parent must be on main")
    return state


def _remote_main_oid() -> str:
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--exit-code", "origin", "refs/heads/main"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DevelopmentRuntimePatchError("Cannot query real origin/main for E0-DLP") from exc
    fields = result.stdout.strip().split()
    if result.returncode != 0 or len(fields) != 2 or fields[1] != "refs/heads/main":
        raise DevelopmentRuntimePatchError("Cannot verify real origin/main for E0-DLP")
    return _require_commit(fields[0], context="remote origin/main")


def _parent_publication(head: str, *, verify_remote: bool) -> dict[str, Any]:
    tracking_ref = EXPECTED_PUBLISHED_REF
    tracking_oid = _require_commit(_git("rev-parse", tracking_ref), context=tracking_ref)
    if tracking_oid != head:
        raise DevelopmentRuntimePatchError("Patch parent must be published unchanged on origin/main")
    remote_oid = _remote_main_oid() if verify_remote else None
    if remote_oid is not None and remote_oid != head:
        raise DevelopmentRuntimePatchError("Patch parent differs from real origin/main")
    return {
        "tracking_ref": tracking_ref,
        "tracking_oid": tracking_oid,
        "remote_ref": "refs/heads/main",
        "remote_oid": remote_oid,
        "published_head": head,
        "execution_head": head,
        "published_head_is_ancestor_of_execution": True,
        "local_tracking_verified": True,
        "remote_verified": remote_oid is not None,
    }


def _validate_record_at_head(record: Mapping[str, Any], head: str, *, context: str) -> None:
    path = record.get("path")
    if not isinstance(path, str):
        raise DevelopmentRuntimePatchError(f"{context} path is invalid")
    blob = _git_blob(head, path)
    if blob is None:
        raise DevelopmentRuntimePatchError(f"{context} is not committed at {head}: {path}")
    if record.get("bytes") != len(blob) or record.get("sha256") != _sha256_bytes(blob):
        raise DevelopmentRuntimePatchError(f"{context} differs from Git-at-H: {path}")


def _base_record_candidates(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    runtime_contract = cast(Mapping[str, Any], payload["runtime_contract"])
    for key in ("config", "schema"):
        records.append(cast(Mapping[str, Any], runtime_contract[key]))
    for field in ("components", "runtime_dependencies", "parents"):
        records.extend(cast(Sequence[Mapping[str, Any]], payload[field]))
    for field in ("common_origin", "expert_state"):
        artifact = cast(Mapping[str, Any], payload[field])
        records.extend(cast(Sequence[Mapping[str, Any]], artifact["completion_records"]))
        dvc = cast(Mapping[str, Any], artifact["dvc"])
        pointer_path = str(dvc["pointer_path"])
        blob = _git_blob(str(cast(Mapping[str, Any], payload["locked_repository"])["head"]), pointer_path)
        if blob is not None:
            records.append(
                {
                    "path": pointer_path,
                    "role": f"{field}_dvc_pointer",
                    "bytes": len(blob),
                    "sha256": _sha256_bytes(blob),
                }
            )
    return records


def _base_git_at_h_records(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    locked = cast(Mapping[str, Any], payload["locked_repository"])
    locked_head = _require_commit(locked.get("head"), context="base locked H")
    component_paths = {
        str(record["path"])
        for field in ("components", "runtime_dependencies")
        for record in cast(Sequence[Mapping[str, Any]], payload[field])
    }
    observed: dict[str, dict[str, Any]] = {}
    for record in _base_record_candidates(payload):
        path = str(record.get("path", ""))
        blob = _git_blob(locked_head, path)
        if blob is None:
            if path in component_paths:
                raise DevelopmentRuntimePatchError(
                    f"Base component is absent from locked Git-at-H: {path}"
                )
            continue
        if record.get("bytes") != len(blob) or record.get("sha256") != _sha256_bytes(blob):
            raise DevelopmentRuntimePatchError(f"Base record differs from Git-at-H: {path}")
        normalized = dict(record)
        prior = observed.get(path)
        if prior is not None and (
            prior["bytes"] != normalized["bytes"]
            or prior["sha256"] != normalized["sha256"]
        ):
            raise DevelopmentRuntimePatchError(f"Conflicting base Git records: {path}")
        observed[path] = normalized
    required_runtime = {
        str(cast(Mapping[str, Any], cast(Mapping[str, Any], payload["runtime_contract"])[key])["path"])
        for key in ("config", "schema")
    }
    if not component_paths.union(required_runtime).issubset(observed):
        raise DevelopmentRuntimePatchError("Base Git-at-H record set is incomplete")
    return [observed[path] for path in sorted(observed)]


def _base_lock_snapshot(
    base_lock_path: Path = DEFAULT_LOCK_PATH,
    base_lock_schema: Path = DEFAULT_LOCK_SCHEMA,
) -> dict[str, Any]:
    payload = load_json_mapping(base_lock_path)
    schema = load_json_mapping(base_lock_schema)
    validate_development_runtime_lock_payload(payload, schema)
    lock_commit = _introduced_commit(base_lock_path)
    lock_record = _file_record(base_lock_path, role="base_development_runtime_lock")
    schema_record = _file_record(base_lock_schema, role="base_development_runtime_lock_schema")
    lock_blob = _git_blob(lock_commit, lock_record["path"])
    if lock_blob is None or len(lock_blob) != lock_record["bytes"] or _sha256_bytes(lock_blob) != lock_record["sha256"]:
        raise DevelopmentRuntimePatchError("Published base E0-DL bytes changed")
    schema_blob = _git_blob(lock_commit, schema_record["path"])
    if (
        schema_blob is None
        or len(schema_blob) != schema_record["bytes"]
        or _sha256_bytes(schema_blob) != schema_record["sha256"]
    ):
        raise DevelopmentRuntimePatchError("Published base E0-DL schema bytes changed")
    locked_head = _require_commit(
        cast(Mapping[str, Any], payload["locked_repository"]).get("head"),
        context="base locked H",
    )
    if (
        lock_commit != EXPECTED_BASE_LOCK_COMMIT
        or locked_head != EXPECTED_BASE_LOCKED_HEAD
        or lock_record["bytes"] != EXPECTED_BASE_LOCK_BYTES
        or lock_record["sha256"] != EXPECTED_BASE_LOCK_SHA256
        or payload.get("canonical_origin", {}).get("identity_sha256")
        != EXPECTED_CANONICAL_ORIGIN_IDENTITY_SHA256
        or cast(Mapping[str, Any], payload["planned_artifacts"]).get("count")
        != EXPECTED_PATH_COUNT
        or cast(Mapping[str, Any], payload["planned_artifacts"]).get("sha256")
        != EXPECTED_PATH_DIGEST
    ):
        raise DevelopmentRuntimePatchError("Immutable base E0-DL anchors drifted")
    _require_ancestor(locked_head, lock_commit)
    git_records = _base_git_at_h_records(payload)
    return {
        "payload": payload,
        "lock": lock_record,
        "schema": schema_record,
        "lock_commit": lock_commit,
        "locked_repository_head": locked_head,
        "lock_version": BASE_LOCK_VERSION,
        "status": "locked",
        "git_at_h_record_count": len(git_records),
        "git_at_h_records_sha256": _record_digest(git_records),
        "git_at_h_records": git_records,
        "base_lock_unchanged": True,
    }


def _validate_base_physical_authority(
    base: Mapping[str, Any],
    *,
    runtime_config: Path,
    runtime_schema: Path,
    require_physical_artifacts: bool,
) -> dict[str, Any]:
    """Re-run every non-component E0-DL gate against current physical inputs."""
    payload = cast(Mapping[str, Any], base["payload"])
    runtime = load_yaml_mapping(runtime_config)
    runtime_schema_payload = load_json_mapping(runtime_schema)
    try:
        validate_json_schema(
            runtime,
            runtime_schema_payload,
            instance_path="$.development_runtime",
        )
    except ClosureContractError as exc:
        raise DevelopmentRuntimePatchError(str(exc)) from exc
    _runtime_paths_match_contract(
        runtime,
        runtime_config=runtime_config,
        runtime_schema=runtime_schema,
        lock_schema=DEFAULT_LOCK_SCHEMA,
        lock_path=DEFAULT_LOCK_PATH,
    )
    _validate_runtime_prelock_contract(
        runtime,
        runtime_schema_payload,
        require_physical_artifacts=require_physical_artifacts,
    )
    expected_runtime_contract = {
        "config": _file_record(runtime_config, role="development_runtime_config"),
        "schema": _file_record(runtime_schema, role="development_runtime_schema"),
        "status": EXPECTED_RUNTIME_STATUS,
    }
    if payload.get("runtime_contract") != expected_runtime_contract:
        raise DevelopmentRuntimePatchError(
            "Current runtime config/schema differ from immutable E0-DL"
        )
    if payload.get("canonical_origin") != canonical_origin_identity(runtime):
        raise DevelopmentRuntimePatchError("Canonical origin drifted from immutable E0-DL")

    locked_restored = cast(Sequence[Any], payload["restored_development_sources"])
    if require_physical_artifacts:
        restored = restored_development_source_records(runtime)
        if locked_restored != restored:
            raise DevelopmentRuntimePatchError("Restored development sources drifted")
    else:
        restored = _validate_restored_source_lock_metadata(locked_restored, runtime)

    observed_common = common_origin_lock_record(
        runtime,
        require_physical_artifact=require_physical_artifacts,
    )
    observed_expert = expert_state_lock_record(
        runtime,
        runtime_config=runtime_config,
        runtime_schema=runtime_schema,
        require_physical_artifact=require_physical_artifacts,
    )
    locked_common = cast(Mapping[str, Any], payload["common_origin"])
    locked_expert = cast(Mapping[str, Any], payload["expert_state"])
    if require_physical_artifacts:
        if locked_common != observed_common:
            raise DevelopmentRuntimePatchError("Common-origin E0-DL artifact drifted")
        if locked_expert != observed_expert:
            raise DevelopmentRuntimePatchError("Expert-state E0-DL artifact drifted")
        common = observed_common
        expert = observed_expert
        expected_parents = parent_records(
            runtime,
            common_origin=common,
            expert_state=expert,
        )
        _require_exact_record_set(
            cast(Sequence[Any], payload["parents"]),
            expected_parents,
            context="E0-DLP.base_parents",
        )
    else:
        _locked_artifact_matches_observed_metadata(
            locked_common,
            observed_common,
            context="E0-DLP.base_common_origin",
        )
        _locked_artifact_matches_observed_metadata(
            locked_expert,
            observed_expert,
            context="E0-DLP.base_expert_state",
        )
        common = dict(locked_common)
        expert = dict(locked_expert)
        _validate_parent_lock_metadata(
            cast(Sequence[Any], payload["parents"]),
            runtime,
            common_origin=common,
            expert_state=expert,
            restored_sources=restored,
        )

    validate_dvc_remote_verification_evidence(
        cast(Mapping[str, Any], payload["dvc_remote_verification"]),
        runtime=runtime,
        common_origin=common,
        expert_state=expert,
        verify_current_remote_config=require_physical_artifacts,
    )
    expected_planned = planned_artifact_records(
        runtime,
        locked_head=str(base["locked_repository_head"]),
        expert_state=expert,
    )
    if payload.get("planned_artifacts") != expected_planned:
        raise DevelopmentRuntimePatchError("E0-DL planned-artifact snapshot drifted")
    verification = cast(Mapping[str, Any], payload["verification"])
    if tuple(cast(Mapping[str, Any], verification["full_type_check"])["command"]) != TYPE_CHECK_COMMAND:
        raise DevelopmentRuntimePatchError("Base E0-DL type-check command drifted")
    if tuple(cast(Mapping[str, Any], verification["focused_tests"])["command"]) != focused_test_command(runtime):
        raise DevelopmentRuntimePatchError("Base E0-DL focused-test command drifted")
    if require_physical_artifacts:
        current_environment = environment_payload(
            str(cast(Mapping[str, Any], payload["environment"])["device"]),
            runtime,
        )
        if payload.get("environment") != current_environment:
            raise DevelopmentRuntimePatchError("Base E0-DL execution environment drifted")
    return {
        "runtime": runtime,
        "common_origin": common,
        "expert_state": expert,
        "restored_sources": restored,
        "planned_artifacts": expected_planned,
        "physical_artifacts_verified": require_physical_artifacts,
        "base_dvc_remote_evidence_verified": True,
    }


def _base_component_records(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for field in ("components", "runtime_dependencies"):
        for raw in cast(Sequence[Mapping[str, Any]], payload[field]):
            path = str(raw["path"])
            record = dict(raw)
            prior = records.get(path)
            if prior is not None and (
                prior["bytes"] != record["bytes"] or prior["sha256"] != record["sha256"]
            ):
                raise DevelopmentRuntimePatchError(f"Conflicting base component record: {path}")
            records[path] = record
    return records


def _base_component_drift(payload: Mapping[str, Any], patch_head: str) -> dict[str, Any]:
    base_records = _base_component_records(payload)
    if not set(BASE_COMPONENT_DRIFT_ALLOWLIST).issubset(base_records):
        raise DevelopmentRuntimePatchError("Base drift allowlist is not present in E0-DL components")
    observed: list[str] = []
    drift_records: list[dict[str, Any]] = []
    for path in sorted(base_records):
        base = base_records[path]
        current = _file_record(path, role="patched_base_component")
        changed = base["bytes"] != current["bytes"] or base["sha256"] != current["sha256"]
        if changed:
            observed.append(path)
            _validate_record_at_head(current, patch_head, context="patched base component")
            drift_records.append(
                {
                    "path": path,
                    "base_bytes": base["bytes"],
                    "base_sha256": base["sha256"],
                    "patch_bytes": current["bytes"],
                    "patch_sha256": current["sha256"],
                }
            )
    expected = list(BASE_COMPONENT_DRIFT_ALLOWLIST)
    if observed != sorted(expected):
        raise DevelopmentRuntimePatchError(
            f"Base component drift differs from the exact E0-DLP allowlist: {observed}"
        )
    records = sorted(drift_records, key=lambda record: str(record["path"]))
    return {
        "count": len(records),
        "allowlist": sorted(expected),
        "observed_paths": observed,
        "records": records,
        "records_sha256": _record_digest(records),
        "only_allowlisted_base_components_changed": True,
    }


def _patch_component_records(patch_head: str) -> list[dict[str, Any]]:
    records = [
        _file_record(path, role=role)
        for path, role in sorted(PATCH_COMPONENT_ROLES.items())
    ]
    for record in records:
        _validate_record_at_head(record, patch_head, context="E0-DLP patch component")
    return records


def _patch_components_record(patch_head: str) -> dict[str, Any]:
    records = _patch_component_records(patch_head)
    paths = [str(record["path"]) for record in records]
    return {
        "count": len(records),
        "paths": paths,
        "paths_sha256": _path_digest(paths),
        "records": records,
        "records_sha256": _record_digest(records),
    }


def patch_lock_artifact_record() -> dict[str, Any]:
    return {
        "count": 1,
        "path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "role": "external_development_runtime_patch_lock",
        "self_hash_policy": "verified_from_committed_and_published_bytes",
    }


def _git_diff_exact(
    base_commit: str,
    patch_head: str,
    *,
    expected_paths: Sequence[str],
    expected_modified_paths: frozenset[str],
) -> dict[str, Any]:
    raw = _git("diff", "--name-status", "--no-renames", base_commit, patch_head)
    entries: list[dict[str, str]] = []
    for line in raw.splitlines():
        fields = line.split("\t")
        if len(fields) != 2 or fields[0] not in {"A", "M"}:
            raise DevelopmentRuntimePatchError(f"E0-DLP forbids this Git diff entry: {line}")
        entries.append({"status": fields[0], "path": fields[1]})
    entries.sort(key=lambda record: record["path"])
    paths = [record["path"] for record in entries]
    if paths != list(expected_paths):
        raise DevelopmentRuntimePatchError(
            f"Patch-parent diff differs from the exact E0-DLP allowlist: {paths}"
        )
    expected_entries = [
        {
            "status": "M" if path in expected_modified_paths else "A",
            "path": path,
        }
        for path in expected_paths
    ]
    if entries != expected_entries:
        raise DevelopmentRuntimePatchError(
            f"E0-DLP Git diff status/path records drifted: {entries}"
        )
    return {
        "base_commit": base_commit,
        "patch_head": patch_head,
        "entries": entries,
        "paths": paths,
        "paths_sha256": _path_digest(paths),
        "only_allowed_additions_and_modifications": True,
    }


def _git_diff(base_commit: str, patch_head: str) -> dict[str, Any]:
    modified = frozenset({*BASE_COMPONENT_DRIFT_ALLOWLIST, MODELS_OWNER_PATH.as_posix()})
    return _git_diff_exact(
        base_commit,
        patch_head,
        expected_paths=PATCH_PARENT_DIFF_ALLOWLIST,
        expected_modified_paths=modified,
    )


def _publication_sequence(base_commit: str, patch_head: str) -> dict[str, Any]:
    patch_parents = _git("rev-list", "--parents", "-n", "1", patch_head).split()
    if (
        len(patch_parents) != 2
        or patch_parents[0] != patch_head
        or patch_parents[1] != EXPECTED_ACTIVATION_HEAD
    ):
        raise DevelopmentRuntimePatchError(
            "R-DLP must be a direct non-merge child of the sealed H-DLP commit"
        )
    activation_head = _require_commit(
        patch_parents[1], context="H-DLP activation head"
    )
    activation_parents = _git(
        "rev-list", "--parents", "-n", "1", activation_head
    ).split()
    if (
        len(activation_parents) != 2
        or activation_parents[0] != activation_head
        or activation_parents[1] != EXPECTED_ADOPTION_HEAD
    ):
        raise DevelopmentRuntimePatchError(
            "H-DLP must remain a direct non-merge child of the sealed A-DLP commit"
        )
    adoption_head = _require_commit(
        activation_parents[1], context="A-DLP adoption head"
    )
    adoption_parents = _git(
        "rev-list", "--parents", "-n", "1", adoption_head
    ).split()
    if (
        len(adoption_parents) != 2
        or adoption_parents[0] != adoption_head
        or adoption_parents[1] != base_commit
    ):
        raise DevelopmentRuntimePatchError(
            "A-DLP must remain a direct non-merge child of the E0-DL lock commit"
        )
    _require_ancestor(base_commit, adoption_head)
    _require_ancestor(adoption_head, activation_head)
    _require_ancestor(activation_head, patch_head)
    adoption_modified = frozenset(
        {
            "src/experiments/build_closure_pipe_sequences.py",
            "tests/test_build_closure_pipe_sequences.py",
            MODELS_OWNER_PATH.as_posix(),
        }
    )
    adoption_diff = _git_diff_exact(
        base_commit,
        adoption_head,
        expected_paths=PATCH_ADOPTION_DIFF_ALLOWLIST,
        expected_modified_paths=adoption_modified,
    )
    activation_diff = _git_diff_exact(
        adoption_head,
        activation_head,
        expected_paths=PATCH_ACTIVATION_PATHS,
        expected_modified_paths=frozenset(PATCH_ACTIVATION_PATHS),
    )
    repair_diff = _git_diff_exact(
        activation_head,
        patch_head,
        expected_paths=PATCH_REPAIR_PATHS,
        expected_modified_paths=frozenset(PATCH_REPAIR_PATHS),
    )
    aggregate_diff = _git_diff(base_commit, patch_head)
    return {
        "base_commit": base_commit,
        "adoption_head": adoption_head,
        "activation_head": activation_head,
        "patch_head": patch_head,
        "adoption_is_direct_first_parent_of_activation": True,
        "activation_is_direct_first_parent_of_patch": True,
        "base_is_ancestor_of_adoption": True,
        "adoption_is_ancestor_of_activation": True,
        "activation_is_ancestor_of_patch": True,
        "base_to_adoption": adoption_diff,
        "adoption_to_activation": activation_diff,
        "activation_to_patch": repair_diff,
        "base_to_patch": aggregate_diff,
    }


def _physical_record_matches(record: Mapping[str, Any], *, context: str) -> None:
    expected = _file_record(str(record.get("path", "")), role=str(record.get("role", "")))
    if dict(record) != expected:
        raise DevelopmentRuntimePatchError(f"{context} differs from physical bytes")


def _require_expected_seed_final(path: str | Path) -> None:
    relative = _relative(path)
    expected = EXPECTED_SEED_FINALS.get(relative)
    if expected is None:
        raise DevelopmentRuntimePatchError(f"Unexpected seed-1729 final path: {relative}")
    physical = _resolve(relative)
    if not physical.is_file():
        raise DevelopmentRuntimePatchError(f"Seed-1729 final is missing: {relative}")
    expected_bytes, expected_sha256 = expected
    if physical.stat().st_size != expected_bytes or _sha256_file(physical) != expected_sha256:
        raise DevelopmentRuntimePatchError(
            f"Seed-1729 final differs from its pre-patch audit anchor: {relative}"
        )


def _validate_seed_final_inventory() -> None:
    for path in EXPECTED_SEED_FINALS:
        _require_expected_seed_final(path)
    report_dir = _resolve(SEED_MANIFEST_PATH).parent
    model_dir = _resolve(SEED_CHECKPOINT_PATHS[0]).parent
    state_dir = _resolve(SEED_STATE_PATH).parent
    expected_report_names = {
        SEED_MANIFEST_PATH.name,
        *(path.name for path in SEED_LIGHTWEIGHT_PATHS),
    }
    expected_model_names = {path.name for path in SEED_CHECKPOINT_PATHS}
    expected_state_names = {SEED_STATE_PATH.name, SEED_STATE_POINTER_PATH.name}
    observed_report_names = {path.name for path in report_dir.iterdir() if path.is_file()}
    observed_model_names = {path.name for path in model_dir.iterdir() if path.is_file()}
    observed_state_names = {path.name for path in state_dir.iterdir() if path.is_file()}
    if observed_report_names != expected_report_names:
        raise DevelopmentRuntimePatchError("Seed-1729 report final inventory drifted")
    if observed_model_names != expected_model_names:
        raise DevelopmentRuntimePatchError("Seed-1729 checkpoint final inventory drifted")
    if observed_state_names != expected_state_names:
        raise DevelopmentRuntimePatchError("Seed-1729 state/DVC final inventory drifted")
    forbidden_markers = (".tmp", ".partial", ".part")
    for directory in (report_dir, model_dir, state_dir):
        if any(
            marker in path.name
            for path in directory.iterdir()
            for marker in forbidden_markers
        ):
            raise DevelopmentRuntimePatchError("Seed-1729 temporary/partial file is present")


def _historical_blob(record: Mapping[str, Any], *, context: str) -> bytes:
    path = str(record.get("path", ""))
    blob = _git_blob(EXPECTED_BASE_LOCK_COMMIT, path)
    if (
        blob is None
        or len(blob) != record.get("bytes")
        or _sha256_bytes(blob) != record.get("sha256")
    ):
        raise DevelopmentRuntimePatchError(
            f"{context} differs from its Git-locked E0-DL bytes"
        )
    return blob


def _is_terminal_manifest_write(statement: ast.stmt) -> bool:
    if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
        return False
    call = statement.value
    if (
        not isinstance(call.func, ast.Name)
        or call.func.id != "_write_json_atomic"
        or len(call.args) != 2
        or call.keywords
        or not isinstance(call.args[0], ast.Name)
        or call.args[0].id != "payload"
    ):
        return False
    manifest_path = call.args[1]
    return (
        isinstance(manifest_path, ast.Subscript)
        and isinstance(manifest_path.value, ast.Name)
        and manifest_path.value.id == "paths"
        and isinstance(manifest_path.slice, ast.Constant)
        and manifest_path.slice.value == "anfis_manifest_template"
    )


def _verify_historical_completion_order_producer() -> None:
    producer_blob = _historical_blob(
        HISTORICAL_ANFIS_SCRIPT_RECORD,
        context="Seed-1729 historical ANFIS producer",
    )
    regression_blob = _historical_blob(
        HISTORICAL_ANFIS_TEST_RECORD,
        context="Seed-1729 historical completion-order regression",
    )
    try:
        producer_tree = ast.parse(producer_blob.decode("utf-8"))
        regression_tree = ast.parse(regression_blob.decode("utf-8"))
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise DevelopmentRuntimePatchError(
            "Git-locked seed-1729 completion-order evidence is not parseable Python"
        ) from exc
    writers = [
        node
        for node in producer_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "write_anfis_slot_bundle"
    ]
    if len(writers) != 1 or len(writers[0].body) < 2:
        raise DevelopmentRuntimePatchError(
            "Git-locked seed-1729 producer lacks one closed slot-bundle writer"
        )
    writer = writers[0]
    terminal_writes = [
        node
        for node in ast.walk(writer)
        if isinstance(node, ast.stmt) and _is_terminal_manifest_write(node)
    ]
    terminal_return = writer.body[-1]
    if (
        len(terminal_writes) != 1
        or terminal_writes[0] is not writer.body[-2]
        or not isinstance(terminal_return, ast.Return)
        or not isinstance(terminal_return.value, ast.Name)
        or terminal_return.value.id != "payload"
    ):
        raise DevelopmentRuntimePatchError(
            "Git-locked seed-1729 producer does not write its manifest as the final bundle write"
        )
    regressions = [
        node
        for node in regression_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "test_slot_bundle_writes_completion_manifest_last"
    ]
    if len(regressions) != 1:
        raise DevelopmentRuntimePatchError(
            "Git-locked seed-1729 completion-order regression is absent or duplicated"
        )


def _completion_order_evidence_record(
    *, bundle_records_sha256: str, models_owner_hash_value: str
) -> dict[str, Any]:
    if SHA256_RE.fullmatch(bundle_records_sha256) is None or re.fullmatch(
        r"[0-9a-f]{32}\.dir", models_owner_hash_value
    ) is None:
        raise DevelopmentRuntimePatchError(
            "Seed-1729 content-addressed completion evidence is malformed"
        )
    return {
        "evidence_version": "closure_completion_order_evidence_v1",
        "method": "git_locked_producer_control_flow_and_content_addressed_bundle_v1",
        "producer_commit": EXPECTED_BASE_LOCK_COMMIT,
        "producer_record": dict(HISTORICAL_ANFIS_SCRIPT_RECORD),
        "producer_test_record": dict(HISTORICAL_ANFIS_TEST_RECORD),
        "writer_function": "write_anfis_slot_bundle",
        "historical_regression": "test_slot_bundle_writes_completion_manifest_last",
        "manifest_write_function": "_write_json_atomic",
        "manifest_path_key": "anfis_manifest_template",
        "manifest_write_is_final_output_write": True,
        "manifest_completion_marker_verified": True,
        "manifest_output_record_count": 13,
        "physical_final_count": 14,
        "bundle_records_sha256": bundle_records_sha256,
        "state_sha256": EXPECTED_SEED_FINALS[SEED_STATE_PATH.as_posix()][1],
        "state_dvc_md5": EXPECTED_SEED_STATE_MD5,
        "models_owner_hash_value": models_owner_hash_value,
        "producer_control_flow_verified": True,
        "producer_regression_verified": True,
        "content_addressed_bundle_verified": True,
        "temporary_or_partial_file_count": 0,
        "filesystem_mtime_used": False,
        "dvc_materialization_metadata_non_authoritative": True,
        "portable_across_fresh_clone_and_dvc_materialization": True,
    }


def _validate_manifest_dependency_at_execution(
    record: Mapping[str, Any], execution_head: str
) -> None:
    path = str(record.get("path", ""))
    blob = _git_blob(execution_head, path)
    if blob is not None:
        if record.get("bytes") != len(blob) or record.get("sha256") != _sha256_bytes(blob):
            raise DevelopmentRuntimePatchError(
                f"Seed-1729 dependency differs from Git at its execution HEAD: {path}"
            )
        return
    _physical_record_matches(record, context=f"seed dependency {path}")


def _sample_key_digest(frame: pd.DataFrame) -> str:
    digest = hashlib.sha256()
    for row in frame.loc[:, ["source_id", "site_id", "year_month"]].to_dict(orient="records"):
        digest.update(
            json.dumps(
                [str(row["source_id"]), str(row["site_id"]), str(row["year_month"])],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        digest.update(b"\n")
    return digest.hexdigest()


def _validate_sample_files(manifest: Mapping[str, Any]) -> None:
    sampling = cast(Mapping[str, Mapping[str, Any]], manifest["sampling"])
    for module, path in zip(MODULES, SEED_LIGHTWEIGHT_PATHS[:3], strict=True):
        frame = pd.read_csv(_resolve(path), dtype=str)
        expected_columns = [
            "source_id",
            "site_id",
            "year_month",
            "module",
            "module_seed",
            "rank_sha256",
        ]
        if frame.columns.tolist() != expected_columns or len(frame) != 4096:
            raise DevelopmentRuntimePatchError(f"Seed-1729 sample schema/count drifted: {module}")
        if bool(frame.duplicated(["source_id", "site_id", "year_month"], keep=False).any()):
            raise DevelopmentRuntimePatchError(f"Seed-1729 sample keys are duplicated: {module}")
        if set(frame["source_id"]) != {"wqp"} or set(frame["module"]) != {module}:
            raise DevelopmentRuntimePatchError(f"Seed-1729 sample identity drifted: {module}")
        if set(frame["module_seed"]) != {str(MODULE_SEEDS[module])}:
            raise DevelopmentRuntimePatchError(f"Seed-1729 module seed drifted: {module}")
        if any(value > "2018-12" for value in frame["year_month"]):
            raise DevelopmentRuntimePatchError(f"Seed-1729 sample exceeds training cutoff: {module}")
        if any(
            value != value.strip() or value != unicodedata.normalize("NFC", value)
            for column in expected_columns
            for value in frame[column]
        ):
            raise DevelopmentRuntimePatchError(f"Seed-1729 sample normalization drifted: {module}")
        ranks: list[str] = []
        for row in frame.to_dict(orient="records"):
            payload = json.dumps(
                [MODULE_SEEDS[module], row["source_id"], row["site_id"], row["year_month"]],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            ranks.append(_sha256_bytes(payload))
        if frame["rank_sha256"].tolist() != ranks or ranks != sorted(ranks):
            raise DevelopmentRuntimePatchError(f"Seed-1729 rank order drifted: {module}")
        audit = sampling[module]
        if audit.get("selected_rows") != 4096 or audit.get("selected_keys_sha256") != _sample_key_digest(frame):
            raise DevelopmentRuntimePatchError(f"Seed-1729 sampling digest drifted: {module}")


def _audit_seed_state(path: Path) -> dict[str, Any]:
    frame = pd.read_parquet(_resolve(path))
    if frame.columns.tolist() != list(STATE_ALLOWLIST):
        raise DevelopmentRuntimePatchError("Seed-1729 state allowlist drifted")
    gate = load_development_gate()
    assert_development_frame(frame, gate, role_column="time_role", allowed_roles=DEVELOPMENT_ROLES)
    if frame.empty or bool(frame.duplicated(["source_id", "site_id", "year_month"], keep=False).any()):
        raise DevelopmentRuntimePatchError("Seed-1729 state keys are empty or duplicated")
    keys = set(zip(frame["source_id"].astype(str), frame["site_id"].astype(str), strict=True))
    holdout_overlap = keys.intersection(gate.holdout_keys)
    unknown = keys.difference(gate.development_keys).difference(gate.holdout_keys)
    if len(keys) != 353 or holdout_overlap or unknown or keys != gate.development_keys:
        raise DevelopmentRuntimePatchError("Seed-1729 state assignment geometry drifted")
    for column in LEVEL_COLUMNS:
        numeric = pd.to_numeric(frame[column], errors="coerce")
        if bool(numeric.isna().any()) or not bool(numeric.between(0.0, 1.0).all()):
            raise DevelopmentRuntimePatchError(f"Seed-1729 level/sigma range drifted: {column}")
    for column in DELTA_COLUMNS:
        numeric = pd.to_numeric(frame[column], errors="coerce")
        if bool(numeric.isna().any()) or not bool(numeric.between(-1.0, 1.0).all()):
            raise DevelopmentRuntimePatchError(f"Seed-1729 signed delta range drifted: {column}")
    expected_delta_rows = closure_state_deltas(
        "P1",
        frame.loc[
            :,
            ["source_id", "site_id", "year_month", "yN_adaptive", "yF_adaptive", "yT_no_chla_adaptive"],
        ].to_dict(orient="records"),
        development_keys=gate.development_keys,
    )
    expected = pd.DataFrame(expected_delta_rows).sort_values(
        ["source_id", "site_id", "year_month"], kind="mergesort"
    ).reset_index(drop=True)
    observed = frame.loc[
        :,
        ["source_id", "site_id", "year_month", *DELTA_COLUMNS, "delta_previous_month_missing"],
    ].sort_values(["source_id", "site_id", "year_month"], kind="mergesort").reset_index(drop=True)
    for column in DELTA_COLUMNS:
        if not np.array_equal(
            observed[column].to_numpy(dtype=np.float64),
            expected[column].to_numpy(dtype=np.float64),
        ):
            raise DevelopmentRuntimePatchError(f"Seed-1729 exact-month delta drifted: {column}")
    if observed["delta_previous_month_missing"].tolist() != expected[
        "delta_previous_month_missing"
    ].tolist():
        raise DevelopmentRuntimePatchError("Seed-1729 missing-previous flags drifted")
    months = frame["year_month"].astype(str)
    if months.max() > "2021-12":
        raise DevelopmentRuntimePatchError("Seed-1729 materializes a row after 2021-12")
    counts = frame["time_role"].astype(str).value_counts()
    role_counts = {role: int(counts.get(role, 0)) for role in DEVELOPMENT_ROLES}
    return {
        "rows": int(len(frame)),
        "locations": len(keys),
        "minimum_year_month": str(months.min()),
        "maximum_year_month": str(months.max()),
        "role_counts": role_counts,
        "delta_previous_month_missing_count": int(
            frame["delta_previous_month_missing"].sum()
        ),
        "output_allowlist": list(STATE_ALLOWLIST),
        "zero_holdout_overlap": True,
        "zero_unknown_assignment_overlap": True,
        "no_post_2021_materialization": True,
        "future_outcomes_accessed": False,
    }


def _validate_checkpoint(path: Path, module: str) -> None:
    try:
        import torch
    except ImportError as exc:  # pragma: no cover - deployment dependency
        raise DevelopmentRuntimePatchError("Torch is required to audit ANFIS checkpoints") from exc
    try:
        payload = torch.load(_resolve(path), map_location="cpu", weights_only=True)
    except Exception as exc:  # pragma: no cover - torch supplies exception dialect
        raise DevelopmentRuntimePatchError(f"Cannot safely load checkpoint {path}") from exc
    if not isinstance(payload, Mapping):
        raise DevelopmentRuntimePatchError(f"ANFIS checkpoint payload is invalid: {path}")
    expected = {
        "checkpoint_version": "closure_anfis_module_v1",
        "experiment_id": EXPERIMENT_ID,
        "module": module,
        "base_seed": ADOPTED_BASE_SEED,
        "module_seed": MODULE_SEEDS[module],
        "feature_columns": list(MODULE_FEATURES[module]),
        "target_column": MODULE_TARGETS[module],
    }
    if any(payload.get(field) != value for field, value in expected.items()):
        raise DevelopmentRuntimePatchError(f"ANFIS checkpoint identity drifted: {module}")
    if not isinstance(payload.get("model_state_dict"), Mapping):
        raise DevelopmentRuntimePatchError(f"ANFIS checkpoint state is missing: {module}")


def _explicit_pointer_record(artifact_path: Path) -> dict[str, Any]:
    pointer_path = Path(f"{artifact_path.as_posix()}.dvc")
    pointer_record = _file_record(pointer_path, role="adaptive_state_dvc_pointer")
    raw = yaml.safe_load(_resolve(pointer_path).read_text(encoding="utf-8"))
    if (
        not isinstance(raw, Mapping)
        or set(raw) != {"outs"}
        or not isinstance(raw.get("outs"), list)
        or len(raw["outs"]) != 1
    ):
        raise DevelopmentRuntimePatchError("Seed-1729 state DVC pointer is malformed")
    output = raw["outs"][0]
    if (
        not isinstance(output, Mapping)
        or set(output) != {"md5", "size", "hash", "path"}
        or output.get("hash") != "md5"
        or output.get("path") != artifact_path.name
    ):
        raise DevelopmentRuntimePatchError("Seed-1729 state DVC output path drifted")
    md5 = output.get("md5")
    size = output.get("size")
    if not isinstance(md5, str) or MD5_RE.fullmatch(md5) is None:
        raise DevelopmentRuntimePatchError("Seed-1729 state pointer MD5 is invalid")
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise DevelopmentRuntimePatchError("Seed-1729 state pointer size is invalid")
    artifact = _resolve(artifact_path)
    if size != artifact.stat().st_size or md5 != _md5_file(artifact):
        raise DevelopmentRuntimePatchError("Seed-1729 state pointer differs from payload")
    return {
        **pointer_record,
        "owner_strategy": "explicit_pointer",
        "hash_name": "md5",
        "hash_value": md5,
        "size": size,
        "payload_verified": True,
    }


def _models_tree_cache_path(directory_md5: str) -> Path:
    if DIR_MD5_RE.fullmatch(directory_md5) is None:
        raise DevelopmentRuntimePatchError("DVC directory MD5 is invalid")
    digest = directory_md5.removesuffix(".dir")
    return (
        PROJECT_ROOT
        / ".dvc"
        / "cache"
        / "files"
        / "md5"
        / digest[:2]
        / f"{digest[2:]}.dir"
    )


def _load_models_tree_entries(
    directory_md5: str,
) -> tuple[list[dict[str, str]], Path, int]:
    tree_digest = directory_md5.removesuffix(".dir")
    tree_cache = _models_tree_cache_path(directory_md5)
    if not tree_cache.is_file() or _md5_file(tree_cache) != tree_digest:
        raise DevelopmentRuntimePatchError(
            "models.dvc directory cache object is missing or stale"
        )
    tree_cache_bytes = tree_cache.read_bytes()
    try:
        tree_entries_raw = json.loads(tree_cache_bytes.decode("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DevelopmentRuntimePatchError(
            "models.dvc directory cache is invalid"
        ) from exc
    if not isinstance(tree_entries_raw, list):
        raise DevelopmentRuntimePatchError(
            "models.dvc directory cache must contain a list"
        )
    entries: list[dict[str, str]] = []
    observed_paths: set[str] = set()
    cached_payload_size = 0
    for raw_entry in tree_entries_raw:
        if not isinstance(raw_entry, Mapping) or set(raw_entry) != {"md5", "relpath"}:
            raise DevelopmentRuntimePatchError("models.dvc directory entry is invalid")
        relpath = raw_entry.get("relpath")
        entry_md5 = raw_entry.get("md5")
        logical_relpath = Path(str(relpath))
        if (
            not isinstance(relpath, str)
            or not relpath
            or logical_relpath.is_absolute()
            or ".." in logical_relpath.parts
            or logical_relpath.as_posix() != relpath
            or relpath in observed_paths
            or not isinstance(entry_md5, str)
            or MD5_RE.fullmatch(entry_md5) is None
        ):
            raise DevelopmentRuntimePatchError("models.dvc directory relpaths are invalid")
        blob_path = (
            PROJECT_ROOT
            / ".dvc"
            / "cache"
            / "files"
            / "md5"
            / entry_md5[:2]
            / entry_md5[2:]
        )
        if not blob_path.is_file() or _md5_file(blob_path) != entry_md5:
            raise DevelopmentRuntimePatchError(
                f"models.dvc cache blob is missing or stale: {relpath}"
            )
        cached_payload_size += blob_path.stat().st_size
        observed_paths.add(relpath)
        entries.append({"md5": entry_md5, "relpath": relpath})
    if [entry["relpath"] for entry in entries] != sorted(observed_paths):
        raise DevelopmentRuntimePatchError(
            "models.dvc directory entries are not in canonical path order"
        )
    if tree_cache_bytes != _dvc_tree_bytes(entries):
        raise DevelopmentRuntimePatchError(
            "models.dvc directory cache is not canonical DVC JSON"
        )
    return entries, tree_cache, cached_payload_size


def _parse_models_owner_pointer(raw: Any, *, context: str) -> Mapping[str, Any]:
    if (
        not isinstance(raw, Mapping)
        or set(raw) != {"outs"}
        or not isinstance(raw.get("outs"), list)
        or len(raw["outs"]) != 1
    ):
        raise DevelopmentRuntimePatchError(f"{context} is malformed")
    output = raw["outs"][0]
    if (
        not isinstance(output, Mapping)
        or set(output) != {"md5", "size", "nfiles", "hash", "path"}
        or output.get("hash") != "md5"
        or output.get("path") != "models"
    ):
        raise DevelopmentRuntimePatchError(
            f"{context} must be one closed monolithic models owner"
        )
    md5 = output.get("md5")
    size = output.get("size")
    nfiles = output.get("nfiles")
    if not isinstance(md5, str) or DIR_MD5_RE.fullmatch(md5) is None:
        raise DevelopmentRuntimePatchError(f"{context} directory MD5 is invalid")
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise DevelopmentRuntimePatchError(f"{context} size is invalid")
    if isinstance(nfiles, bool) or not isinstance(nfiles, int) or nfiles < 1:
        raise DevelopmentRuntimePatchError(f"{context} nfiles is invalid")
    return output


def _read_models_owner_record() -> dict[str, Any]:
    record = _file_record(MODELS_OWNER_PATH, role="anfis_models_dvc_owner")
    raw = yaml.safe_load(_resolve(MODELS_OWNER_PATH).read_text(encoding="utf-8"))
    output = _parse_models_owner_pointer(raw, context="models.dvc")
    md5 = cast(str, output["md5"])
    size = cast(int, output["size"])
    nfiles = cast(int, output["nfiles"])
    models_root = _resolve("models")
    physical_nodes = list(models_root.rglob("*"))
    if any(path.is_symlink() for path in physical_nodes):
        raise DevelopmentRuntimePatchError(
            "models.dvc physical ownership forbids symbolic links"
        )
    physical_files = sorted(
        (path for path in physical_nodes if path.is_file()),
        key=lambda path: path.relative_to(models_root).as_posix(),
    )
    for path in physical_files:
        try:
            path.resolve().relative_to(models_root.resolve())
        except ValueError as exc:
            raise DevelopmentRuntimePatchError(
                f"models.dvc physical path escapes models/: {path}"
            ) from exc
    physical_size = sum(path.stat().st_size for path in physical_files)
    if nfiles != len(physical_files) or size != physical_size:
        raise DevelopmentRuntimePatchError(
            "models.dvc directory counts differ from the physical models tree"
        )
    tree_entries, tree_cache, cached_payload_size = _load_models_tree_entries(md5)
    entry_by_path = {entry["relpath"]: entry for entry in tree_entries}
    if len(tree_entries) != nfiles or cached_payload_size != size:
        raise DevelopmentRuntimePatchError(
            "models.dvc directory entries do not reconcile to nfiles/size"
        )
    physical_by_path = {
        path.relative_to(models_root).as_posix(): path for path in physical_files
    }
    if set(physical_by_path) != set(entry_by_path):
        raise DevelopmentRuntimePatchError(
            "models.dvc directory entries differ from the physical models paths"
        )
    for relpath, path in physical_by_path.items():
        if _md5_file(path) != entry_by_path[relpath]["md5"]:
            raise DevelopmentRuntimePatchError(
                f"models.dvc entry differs from physical payload: {relpath}"
            )
    for checkpoint in SEED_CHECKPOINT_PATHS:
        relative = checkpoint.relative_to("models").as_posix()
        entry = entry_by_path.get(relative)
        if (
            entry is None
            or entry.get("md5") != SEED_CHECKPOINT_MD5[checkpoint.as_posix()]
            or entry.get("md5") != _md5_file(_resolve(checkpoint))
        ):
            raise DevelopmentRuntimePatchError(
                f"models.dvc does not own the exact seed checkpoint: {checkpoint}"
            )
    return {
        **record,
        "owner_strategy": "monolithic_parent",
        "owned_path": "models",
        "hash_name": "md5",
        "hash_value": md5,
        "size": size,
        "nfiles": nfiles,
        "checkpoint_paths": [path.as_posix() for path in SEED_CHECKPOINT_PATHS],
        "tree_bytes": tree_cache.stat().st_size,
        "tree_cache_sha256": _sha256_file(tree_cache),
        "tree_entry_count": len(tree_entries),
        "tree_entries_sha256": _record_digest(
            [cast(Mapping[str, Any], entry) for entry in tree_entries]
        ),
        "tree_entries": tree_entries,
        "directory_payload_verified": True,
        "checkpoint_membership_verified": True,
        "pointer_metadata_verified": True,
    }


def _base_models_owner_pointer_snapshot() -> dict[str, Any]:
    """Read the immutable base pointer without requiring its historical cache."""
    blob = _git_blob(EXPECTED_BASE_LOCK_COMMIT, MODELS_OWNER_PATH.as_posix())
    if blob is None:
        raise DevelopmentRuntimePatchError("Base models.dvc is absent from E0-DL L")
    try:
        raw = yaml.safe_load(blob.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise DevelopmentRuntimePatchError("Base models.dvc cannot be parsed") from exc
    output = _parse_models_owner_pointer(raw, context="base models.dvc")
    md5 = cast(str, output["md5"])
    size = cast(int, output["size"])
    nfiles = cast(int, output["nfiles"])
    if (
        md5 != EXPECTED_BASE_MODELS_OWNER_MD5
        or size != EXPECTED_BASE_MODELS_OWNER_SIZE
        or nfiles != EXPECTED_BASE_MODELS_OWNER_NFILES
    ):
        raise DevelopmentRuntimePatchError("Base models.dvc anchors drifted")
    return {
        "hash_value": md5,
        "size": size,
        "nfiles": nfiles,
    }


def _models_owner_record() -> dict[str, Any]:
    """Seal the one-time H-DLP owner as base models plus exactly seed 1729."""
    current = _read_models_owner_record()
    base = _base_models_owner_pointer_snapshot()
    current_tree_entries = [
        dict(entry)
        for entry in cast(Sequence[Mapping[str, Any]], current["tree_entries"])
    ]
    current_entries = {
        str(entry["relpath"]): str(entry["md5"])
        for entry in current_tree_entries
    }
    delta_records: list[dict[str, Any]] = []
    expected_delta_paths = {
        path.relative_to("models").as_posix() for path in SEED_CHECKPOINT_PATHS
    }
    base_tree_entries = [
        entry
        for entry in current_tree_entries
        if str(entry["relpath"]) not in expected_delta_paths
    ]
    _validate_base_models_tree_identity(base_tree_entries)
    base_entries = {
        str(entry["relpath"]): str(entry["md5"]) for entry in base_tree_entries
    }
    if (
        current["size"] != EXPECTED_ADOPTED_MODELS_OWNER_SIZE
        or current["nfiles"] != EXPECTED_ADOPTED_MODELS_OWNER_NFILES
        or not all(current_entries.get(path) == md5 for path, md5 in base_entries.items())
        or set(current_entries).difference(base_entries) != expected_delta_paths
    ):
        raise DevelopmentRuntimePatchError(
            "E0-DLP models adoption must equal the base tree plus exactly seed 1729"
        )
    for checkpoint in SEED_CHECKPOINT_PATHS:
        full_path = checkpoint.as_posix()
        relpath = checkpoint.relative_to("models").as_posix()
        expected_bytes, expected_sha256 = EXPECTED_SEED_FINALS[full_path]
        expected_md5 = SEED_CHECKPOINT_MD5[full_path]
        if current_entries.get(relpath) != expected_md5:
            raise DevelopmentRuntimePatchError(
                f"E0-DLP models adoption delta drifted: {full_path}"
            )
        delta_records.append(
            {
                "path": full_path,
                "bytes": expected_bytes,
                "sha256": expected_sha256,
                "md5": expected_md5,
            }
        )
    return {
        **current,
        "base_owner_hash_value": base["hash_value"],
        "base_owner_size": base["size"],
        "base_owner_nfiles": base["nfiles"],
        "base_tree_cache_sha256": EXPECTED_BASE_MODELS_TREE_SHA256,
        "base_tree_entries_sha256": _record_digest(base_tree_entries),
        "adoption_delta_count": len(delta_records),
        "adoption_delta_records": delta_records,
        "adoption_delta_records_sha256": _record_digest(delta_records),
        "base_tree_preserved_exactly": True,
        "adoption_delta_exactly_seed_checkpoints": True,
    }


def _planned_model_relpaths(runtime: Mapping[str, Any]) -> set[str]:
    seeds = cast(Mapping[str, Any], runtime.get("seeds"))
    anfis = cast(Mapping[str, Any], runtime.get("anfis"))
    artifacts = cast(Mapping[str, Any], runtime.get("artifacts"))
    slots = cast(Sequence[Mapping[str, Any]], seeds.get("ordered_slots"))
    modules = cast(Sequence[str], anfis.get("primary_modules"))
    if len(slots) != 5 or tuple(modules) != MODULES:
        raise DevelopmentRuntimePatchError("E0-DLP planned model seed/module set drifted")
    allowed: set[str] = set()
    for slot in slots:
        base_seed = slot.get("base_seed")
        if isinstance(base_seed, bool) or not isinstance(base_seed, int):
            raise DevelopmentRuntimePatchError("E0-DLP model seed is invalid")
        if base_seed != ADOPTED_BASE_SEED:
            for module in modules:
                allowed.add(
                    str(artifacts["anfis_model_template"])
                    .format(
                        base_seed=base_seed,
                        module=MODULE_ARTIFACT_TOKENS[module],
                    )
                    .removeprefix("models/")
                )
        for model_id in ("P0", "P1"):
            for key in ("pipe_model_template", "pipe_checkpoint_template"):
                allowed.add(
                    str(artifacts[key])
                    .format(base_seed=base_seed, model_id=model_id)
                    .removeprefix("models/")
                )
    if any(
        not path.startswith("closure_v1/")
        or Path(path).is_absolute()
        or ".." in Path(path).parts
        or Path(path).as_posix() != path
        for path in allowed
    ):
        raise DevelopmentRuntimePatchError("E0-DLP planned model path escaped its root")
    return allowed


def _validate_locked_models_owner(
    locked_owner: Mapping[str, Any], *, patch_head: str
) -> None:
    """Rebuild the immutable H-DLP owner without requiring historical cache files."""
    _validate_record_at_head(
        locked_owner,
        patch_head,
        context="historical E0-DLP models.dvc adoption owner",
    )
    pointer_blob = _git_blob(patch_head, MODELS_OWNER_PATH.as_posix())
    if pointer_blob is None:
        raise DevelopmentRuntimePatchError("H-DLP models.dvc is absent")
    try:
        pointer_payload = yaml.safe_load(pointer_blob.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise DevelopmentRuntimePatchError("H-DLP models.dvc cannot be parsed") from exc
    output = _parse_models_owner_pointer(pointer_payload, context="H-DLP models.dvc")
    directory_md5 = cast(str, output["md5"])
    directory_size = cast(int, output["size"])
    directory_nfiles = cast(int, output["nfiles"])
    raw_tree_entries = locked_owner.get("tree_entries")
    if not isinstance(raw_tree_entries, Sequence) or isinstance(
        raw_tree_entries, (str, bytes)
    ):
        raise DevelopmentRuntimePatchError("Locked E0-DLP models tree is invalid")
    tree_entries = [
        dict(cast(Mapping[str, Any], entry)) for entry in raw_tree_entries
    ]
    tree_bytes = _dvc_tree_bytes(tree_entries)
    reconstructed_directory_md5 = (
        hashlib.md5(tree_bytes, usedforsecurity=False).hexdigest() + ".dir"
    )
    if (
        len(tree_entries) != directory_nfiles
        or reconstructed_directory_md5 != directory_md5
        or len(tree_bytes) != locked_owner.get("tree_bytes")
        or _sha256_bytes(tree_bytes) != locked_owner.get("tree_cache_sha256")
    ):
        raise DevelopmentRuntimePatchError(
            "H-DLP models tree does not reconcile to its Git-locked pointer"
        )

    expected_checkpoint_paths = [path.as_posix() for path in SEED_CHECKPOINT_PATHS]
    tree_by_path = {
        str(entry["relpath"]): str(entry["md5"]) for entry in tree_entries
    }
    expected_delta_paths = {
        path.relative_to("models").as_posix() for path in SEED_CHECKPOINT_PATHS
    }
    base_tree_entries = [
        entry
        for entry in tree_entries
        if str(entry["relpath"]) not in expected_delta_paths
    ]
    base_tree_bytes = _dvc_tree_bytes(base_tree_entries)
    reconstructed_base_md5 = (
        hashlib.md5(base_tree_bytes, usedforsecurity=False).hexdigest() + ".dir"
    )
    if (
        directory_size != EXPECTED_ADOPTED_MODELS_OWNER_SIZE
        or directory_nfiles != EXPECTED_ADOPTED_MODELS_OWNER_NFILES
        or len(base_tree_entries) != EXPECTED_BASE_MODELS_OWNER_NFILES
        or reconstructed_base_md5 != EXPECTED_BASE_MODELS_OWNER_MD5
        or len(base_tree_bytes) != EXPECTED_BASE_MODELS_TREE_BYTES
        or _sha256_bytes(base_tree_bytes) != EXPECTED_BASE_MODELS_TREE_SHA256
        or set(tree_by_path).difference(
            {str(entry["relpath"]) for entry in base_tree_entries}
        )
        != expected_delta_paths
    ):
        raise DevelopmentRuntimePatchError(
            "H-DLP models owner is not the base tree plus exactly seed 1729"
        )

    delta_records: list[dict[str, Any]] = []
    for checkpoint in SEED_CHECKPOINT_PATHS:
        full_path = checkpoint.as_posix()
        relpath = checkpoint.relative_to("models").as_posix()
        expected_bytes, expected_sha256 = EXPECTED_SEED_FINALS[full_path]
        expected_md5 = SEED_CHECKPOINT_MD5[full_path]
        if tree_by_path.get(relpath) != expected_md5:
            raise DevelopmentRuntimePatchError(
                f"H-DLP checkpoint membership drifted: {full_path}"
            )
        delta_records.append(
            {
                "path": full_path,
                "bytes": expected_bytes,
                "sha256": expected_sha256,
                "md5": expected_md5,
            }
        )

    expected_fields = {
        "owner_strategy": "monolithic_parent",
        "owned_path": "models",
        "hash_name": "md5",
        "hash_value": directory_md5,
        "size": directory_size,
        "nfiles": directory_nfiles,
        "checkpoint_paths": expected_checkpoint_paths,
        "tree_bytes": len(tree_bytes),
        "tree_cache_sha256": _sha256_bytes(tree_bytes),
        "tree_entry_count": len(tree_entries),
        "tree_entries_sha256": _record_digest(tree_entries),
        "tree_entries": tree_entries,
        "base_owner_hash_value": EXPECTED_BASE_MODELS_OWNER_MD5,
        "base_owner_size": EXPECTED_BASE_MODELS_OWNER_SIZE,
        "base_owner_nfiles": EXPECTED_BASE_MODELS_OWNER_NFILES,
        "base_tree_cache_sha256": EXPECTED_BASE_MODELS_TREE_SHA256,
        "base_tree_entries_sha256": _record_digest(base_tree_entries),
        "adoption_delta_count": len(delta_records),
        "adoption_delta_records": delta_records,
        "adoption_delta_records_sha256": _record_digest(delta_records),
        "base_tree_preserved_exactly": True,
        "adoption_delta_exactly_seed_checkpoints": True,
        "directory_payload_verified": True,
        "checkpoint_membership_verified": True,
        "pointer_metadata_verified": True,
    }
    if any(locked_owner.get(key) != value for key, value in expected_fields.items()):
        raise DevelopmentRuntimePatchError(
            "Locked E0-DLP models owner metadata differs from the reconstructed owner"
        )


def _validate_current_models_owner(
    locked_owner: Mapping[str, Any],
    *,
    execution_head: str,
    runtime: Mapping[str, Any],
) -> None:
    current = _read_models_owner_record()
    _validate_record_at_head(
        current,
        execution_head,
        context="current evolving models.dvc owner",
    )
    locked_entries = {
        str(entry["relpath"]): str(entry["md5"])
        for entry in cast(Sequence[Mapping[str, Any]], locked_owner["tree_entries"])
    }
    current_entries = {
        str(entry["relpath"]): str(entry["md5"])
        for entry in cast(Sequence[Mapping[str, Any]], current["tree_entries"])
    }
    if not all(current_entries.get(path) == md5 for path, md5 in locked_entries.items()):
        raise DevelopmentRuntimePatchError(
            "Current models.dvc changed or removed an E0-DLP-adopted model"
        )
    extras = set(current_entries).difference(locked_entries)
    if not extras.issubset(_planned_model_relpaths(runtime)):
        raise DevelopmentRuntimePatchError(
            f"Current models.dvc contains unplanned post-patch model paths: {sorted(extras)}"
        )
    if current.get("sha256") != locked_owner.get("sha256"):
        published_head = _require_commit(
            _git("rev-parse", EXPECTED_PUBLISHED_REF),
            context=EXPECTED_PUBLISHED_REF,
        )
        _require_ancestor(published_head, execution_head)
        published_pointer = _git_blob(published_head, MODELS_OWNER_PATH.as_posix())
        physical_pointer = _resolve(MODELS_OWNER_PATH).read_bytes()
        if published_pointer != physical_pointer:
            raise DevelopmentRuntimePatchError(
                "Evolving models.dvc must be published unchanged on origin/main before the next runner"
            )


def adopted_seed_bundle_record(
    base_snapshot: Mapping[str, Any],
    *,
    require_physical_artifacts: bool = True,
    locked_models_owner: Mapping[str, Any] | None = None,
    execution_head: str | None = None,
    runtime: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate and bind the completed seed-1729 bundle without rewriting it."""
    if require_physical_artifacts:
        _validate_seed_final_inventory()
    else:
        _require_expected_seed_final(SEED_MANIFEST_PATH)
    _verify_historical_completion_order_producer()
    manifest = load_json_mapping(SEED_MANIFEST_PATH)
    expected_top = {
        "manifest_version": "closure_anfis_seed_manifest_v1",
        "status": "completed",
        "slot_status": "available",
        "fit_status": "passed",
        "experiment_id": EXPERIMENT_ID,
        "model_id": "F1",
        "consumer_model_id": "P1",
        "base_seed": ADOPTED_BASE_SEED,
        "development_fit_authorized": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
        "failed_slot_replaced": False,
        "replacement_used": False,
        "completion_marker_written_last": True,
    }
    if any(manifest.get(field) != value for field, value in expected_top.items()):
        raise DevelopmentRuntimePatchError("Seed-1729 manifest identity or seals drifted")
    if manifest.get("module_substreams") != MODULE_SEEDS:
        raise DevelopmentRuntimePatchError("Seed-1729 module substreams drifted")
    authorization = manifest.get("authorization")
    if not isinstance(authorization, Mapping):
        raise DevelopmentRuntimePatchError("Seed-1729 authorization is missing")
    base_lock = cast(Mapping[str, Any], base_snapshot["lock"])
    base_lock_commit = str(base_snapshot["lock_commit"])
    if (
        authorization.get("lock_version") != BASE_LOCK_VERSION
        or authorization.get("lock_path") != base_lock["path"]
        or authorization.get("lock_sha256") != base_lock["sha256"]
        or authorization.get("published_ref") != EXPECTED_PUBLISHED_REF
        or authorization.get("execution_head") != base_lock_commit
        or authorization.get("published_head") != base_lock_commit
        or authorization.get("remote_main_oid") != base_lock_commit
        or authorization.get("development_fit_authorized") is not True
        or authorization.get("evaluation_authorized") is not False
        or authorization.get("e0_u_authorized") is not False
        or authorization.get("future_outcomes_accessed") is not False
    ):
        raise DevelopmentRuntimePatchError("Seed-1729 base E0-DL authorization drifted")
    dependencies = manifest.get("dependencies")
    inputs = manifest.get("inputs")
    if (
        not isinstance(dependencies, Sequence)
        or isinstance(dependencies, (str, bytes))
        or not isinstance(inputs, Sequence)
        or isinstance(inputs, (str, bytes))
    ):
        raise DevelopmentRuntimePatchError("Seed-1729 dependencies/inputs are invalid")
    dependency_by_path: dict[str, Mapping[str, Any]] = {}
    for record in dependencies:
        if not isinstance(record, Mapping):
            raise DevelopmentRuntimePatchError("Seed-1729 dependency record is invalid")
        path = str(record.get("path", ""))
        if path in dependency_by_path:
            raise DevelopmentRuntimePatchError("Seed-1729 dependency paths are duplicated")
        _validate_manifest_dependency_at_execution(record, base_lock_commit)
        dependency_by_path[path] = record
    input_by_path: dict[str, Mapping[str, Any]] = {}
    for record in inputs:
        if not isinstance(record, Mapping):
            raise DevelopmentRuntimePatchError("Seed-1729 input record is invalid")
        path = str(record.get("path", ""))
        if path in input_by_path:
            raise DevelopmentRuntimePatchError("Seed-1729 input paths are duplicated")
        _validate_manifest_dependency_at_execution(record, base_lock_commit)
        input_by_path[path] = record
    script_path = str(cast(Mapping[str, Any], manifest.get("script"))["path"])
    if set(input_by_path) != set(dependency_by_path).difference({script_path}):
        raise DevelopmentRuntimePatchError(
            "Seed-1729 inputs differ from dependencies minus the fitter script"
        )
    for path, record in input_by_path.items():
        if dict(record) != dict(dependency_by_path[path]):
            raise DevelopmentRuntimePatchError(f"Seed-1729 input/dependency drifted: {path}")
    manifest_record = _file_record(SEED_MANIFEST_PATH, role="seed_1729_completion_manifest")
    expected_manifest_bytes, expected_manifest_sha256 = EXPECTED_SEED_FINALS[
        SEED_MANIFEST_PATH.as_posix()
    ]
    if (
        manifest_record["bytes"] != expected_manifest_bytes
        or manifest_record["sha256"] != expected_manifest_sha256
    ):
        raise DevelopmentRuntimePatchError("Seed-1729 completion manifest anchor drifted")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, Sequence) or isinstance(outputs, (str, bytes)):
        raise DevelopmentRuntimePatchError("Seed-1729 output records are invalid")
    expected_output_paths = {
        SEED_STATE_PATH.as_posix(),
        *(path.as_posix() for path in SEED_CHECKPOINT_PATHS),
        *(path.as_posix() for path in SEED_LIGHTWEIGHT_PATHS),
    }
    observed_output_paths: set[str] = set()
    output_records: list[dict[str, Any]] = []
    for raw in outputs:
        if not isinstance(raw, Mapping):
            raise DevelopmentRuntimePatchError("Seed-1729 output record is invalid")
        path = str(raw.get("path", ""))
        if path in observed_output_paths:
            raise DevelopmentRuntimePatchError("Seed-1729 output paths are duplicated")
        _require_expected_seed_final(path)
        metadata = EXPECTED_SEED_OUTPUT_METADATA.get(path)
        if metadata is None:
            raise DevelopmentRuntimePatchError(f"Unexpected seed-1729 output: {path}")
        expected = _file_record(path, role=metadata["role"])
        if "module" in metadata:
            expected["module"] = metadata["module"]
        if dict(raw) != expected:
            raise DevelopmentRuntimePatchError(
                f"Seed-1729 output differs from physical bytes: {raw.get('path')}"
            )
        observed_output_paths.add(path)
        output_records.append(dict(raw))
    if len(output_records) != 13 or observed_output_paths != expected_output_paths:
        raise DevelopmentRuntimePatchError("Seed-1729 output path set drifted")
    if require_physical_artifacts:
        _validate_sample_files(manifest)
        state_audit = _audit_seed_state(SEED_STATE_PATH)
        for module, path in zip(MODULES, SEED_CHECKPOINT_PATHS, strict=True):
            _validate_checkpoint(path, module)
        state_pointer = _explicit_pointer_record(SEED_STATE_PATH)
        if locked_models_owner is None:
            models_owner = _models_owner_record()
        else:
            if execution_head is None or runtime is None:
                raise DevelopmentRuntimePatchError(
                    "Current models owner validation requires execution HEAD and runtime"
                )
            _validate_current_models_owner(
                locked_models_owner,
                execution_head=execution_head,
                runtime=runtime,
            )
            models_owner = dict(locked_models_owner)
    else:
        state_audit = cast(Mapping[str, Any], manifest.get("counts", {}))
        state_pointer = {}
        models_owner = {}
    records_for_digest = [
        manifest_record,
        *sorted(output_records, key=lambda item: str(item["path"])),
    ]
    bundle_records_sha256 = _record_digest(records_for_digest)
    models_owner_hash_value = str(
        models_owner.get("hash_value", EXPECTED_ADOPTED_MODELS_OWNER_MD5)
    )
    completion_order_evidence = _completion_order_evidence_record(
        bundle_records_sha256=bundle_records_sha256,
        models_owner_hash_value=models_owner_hash_value,
    )
    return {
        "base_seed": ADOPTED_BASE_SEED,
        "status": "adopted_prepatch_artifact_without_rematerialization",
        "manifest": manifest_record,
        "state": next(record for record in output_records if record["path"] == SEED_STATE_PATH.as_posix()),
        "checkpoints": [
            next(record for record in output_records if record["path"] == path.as_posix())
            for path in SEED_CHECKPOINT_PATHS
        ],
        "lightweight_outputs": [
            next(record for record in output_records if record["path"] == path.as_posix())
            for path in SEED_LIGHTWEIGHT_PATHS
        ],
        "bundle_records_sha256": bundle_records_sha256,
        "bundle_record_count": 13,
        "physical_final_count": 14,
        "completion_order_evidence": completion_order_evidence,
        "temporary_or_partial_file_count": 0,
        "state_audit": dict(state_audit),
        "dvc": {
            "state_pointer": state_pointer,
            "models_owner": models_owner,
            "registered": require_physical_artifacts,
        },
        "original_authorization": {
            "lock_path": authorization["lock_path"],
            "lock_sha256": authorization["lock_sha256"],
            "execution_head": authorization["execution_head"],
            "published_ref": authorization["published_ref"],
            "published_head": authorization["published_head"],
            "remote_main_oid": authorization["remote_main_oid"],
        },
        "original_manifest_mutated": False,
        "original_seed_rematerialized": False,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
    }


def compatibility_correction_records() -> list[dict[str, Any]]:
    invariants = {
        "scope": "validation_compatibility_only",
        "adopted_base_seed": ADOPTED_BASE_SEED,
        "scientific_runtime_contract_changed": False,
        "sampling_changed": False,
        "model_parameters_changed": False,
        "state_mapping_changed": False,
        "outcome_access_changed": False,
    }
    return [
        {
            "issue_id": "published_ref_compatibility_patch_1",
            "producer_path": "src/experiments/closure_development_runtime_lock.py",
            "consumer_path": "src/experiments/build_closure_pipe_sequences.py",
            "field": "authorization.published_ref",
            "accepted_value": EXPECTED_PUBLISHED_REF,
            "rejected_synthetic_fixture_value": REJECTED_SYNTHETIC_REF,
            **invariants,
        },
        {
            "issue_id": "module_metrics_column_order_compatibility_patch_1",
            "producer_path": "src/experiments/fit_closure_anfis_state.py",
            "consumer_path": "src/experiments/build_closure_pipe_sequences.py",
            "field": "outputs.module_metrics.column_order",
            "accepted_basis": "closed_producer_csv_dialect",
            "rejected_basis": "json_object_insertion_order_after_sorted_serialization",
            "fitted_columns": list(FITTED_MODULE_METRIC_COLUMNS),
            "unavailable_columns": list(UNAVAILABLE_MODULE_METRIC_COLUMNS),
            **invariants,
        },
        {
            "issue_id": "anfis_artifact_path_compatibility_patch_1",
            "producer_path": "src/experiments/fit_closure_anfis_state.py",
            "consumer_path": "src/experiments/build_closure_pipe_sequences.py",
            "inventory_path": "src/experiments/closure_runtime_contract.py",
            "field": "artifacts.anfis_module_path_token",
            "accepted_basis": "locked_runtime_artifact_token",
            "historical_basis": "module_display_name_interpolation",
            "future_module_tokens": dict(MODULE_ARTIFACT_TOKENS),
            "historical_uppercase_paths_restricted_to_seed": ADOPTED_BASE_SEED,
            **invariants,
        },
    ]


def require_adopted_seed_1729_consumer_context(
    manifest: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Authorize the closed historical provenance/path dialect for seed 1729.

    Other manifests return ``None`` and remain subject to current physical
    source bytes and locked artifact slugs.  A manifest that names the exact
    historical validator record must be the immutable seed-1729 completion
    manifest, with its exact historical fitter records and uppercase artifact
    paths, and must have a valid published E0-DLP authority.  There is no
    compatibility fallback.
    """
    dependencies = manifest.get("dependencies")
    inputs = manifest.get("inputs")
    if (
        not isinstance(dependencies, Sequence)
        or isinstance(dependencies, (str, bytes))
        or not isinstance(inputs, Sequence)
        or isinstance(inputs, (str, bytes))
    ):
        return None
    historical_path = str(HISTORICAL_RUNTIME_VALIDATOR_RECORD["path"])
    dependency_matches = [
        record
        for record in dependencies
        if isinstance(record, Mapping) and record.get("path") == historical_path
    ]
    input_matches = [
        record
        for record in inputs
        if isinstance(record, Mapping) and record.get("path") == historical_path
    ]
    exact_dependency_present = any(
        dict(record) == HISTORICAL_RUNTIME_VALIDATOR_RECORD
        for record in dependency_matches
    )
    exact_input_present = any(
        dict(record) == HISTORICAL_RUNTIME_VALIDATOR_RECORD for record in input_matches
    )
    if not exact_dependency_present and not exact_input_present:
        return None
    if (
        len(dependency_matches) != 1
        or len(input_matches) != 1
        or dict(dependency_matches[0]) != HISTORICAL_RUNTIME_VALIDATOR_RECORD
        or dict(input_matches[0]) != HISTORICAL_RUNTIME_VALIDATOR_RECORD
    ):
        raise DevelopmentRuntimePatchError(
            "Seed-1729 historical runtime-validator record is not unique and exact"
        )
    script = manifest.get("script")
    fitter_dependency_matches = [
        record
        for record in dependencies
        if isinstance(record, Mapping)
        and record.get("path") == HISTORICAL_ANFIS_FITTER_FILE["path"]
    ]
    fitter_input_matches = [
        record
        for record in inputs
        if isinstance(record, Mapping)
        and record.get("path") == HISTORICAL_ANFIS_FITTER_FILE["path"]
    ]
    if (
        not isinstance(script, Mapping)
        or dict(script) != HISTORICAL_ANFIS_SCRIPT_RECORD
        or len(fitter_dependency_matches) != 1
        or dict(fitter_dependency_matches[0]) != HISTORICAL_ANFIS_DEPENDENCY_RECORD
        or fitter_input_matches
    ):
        raise DevelopmentRuntimePatchError(
            "Seed-1729 historical fitter provenance is not unique and exact"
        )
    canonical = (
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    ).encode("utf-8")
    expected_manifest_bytes, expected_manifest_sha256 = EXPECTED_SEED_FINALS[
        SEED_MANIFEST_PATH.as_posix()
    ]
    if (
        manifest.get("manifest_version") != "closure_anfis_seed_manifest_v1"
        or manifest.get("base_seed") != ADOPTED_BASE_SEED
        or len(canonical) != expected_manifest_bytes
        or _sha256_bytes(canonical) != expected_manifest_sha256
    ):
        raise DevelopmentRuntimePatchError(
            "Historical runtime-validator compatibility is restricted to the frozen seed 1729 manifest"
        )
    _require_expected_seed_final(SEED_MANIFEST_PATH)
    if dict(manifest) != load_json_mapping(SEED_MANIFEST_PATH):
        raise DevelopmentRuntimePatchError(
            "Seed-1729 consumer payload differs from the frozen physical manifest"
        )
    authorization = manifest.get("authorization")
    if not isinstance(authorization, Mapping) or (
        authorization.get("lock_sha256") != EXPECTED_BASE_LOCK_SHA256
        or authorization.get("execution_head") != EXPECTED_BASE_LOCK_COMMIT
        or authorization.get("published_ref") != EXPECTED_PUBLISHED_REF
        or authorization.get("published_head") != EXPECTED_BASE_LOCK_COMMIT
        or authorization.get("remote_main_oid") != EXPECTED_BASE_LOCK_COMMIT
        or authorization.get("development_fit_authorized") is not True
        or authorization.get("evaluation_authorized") is not False
        or authorization.get("e0_u_authorized") is not False
        or authorization.get("future_outcomes_accessed") is not False
    ):
        raise DevelopmentRuntimePatchError(
            "Seed-1729 historical consumer authorization drifted"
        )
    _validate_record_at_head(
        HISTORICAL_RUNTIME_VALIDATOR_RECORD,
        EXPECTED_BASE_LOCK_COMMIT,
        context="historical seed-1729 runtime validator",
    )
    _validate_record_at_head(
        HISTORICAL_ANFIS_DEPENDENCY_RECORD,
        EXPECTED_BASE_LOCK_COMMIT,
        context="historical seed-1729 ANFIS fitter",
    )
    patch_payload, _ = load_and_validate_development_runtime_patch_lock(
        require_published=True,
        require_physical_artifacts=True,
    )
    adopted = cast(Mapping[str, Any], patch_payload["adopted_seed_bundle"])
    if (
        adopted.get("base_seed") != ADOPTED_BASE_SEED
        or adopted.get("manifest")
        != {
            "path": SEED_MANIFEST_PATH.as_posix(),
            "role": "seed_1729_completion_manifest",
            "bytes": expected_manifest_bytes,
            "sha256": expected_manifest_sha256,
        }
        or adopted.get("original_manifest_mutated") is not False
        or adopted.get("original_seed_rematerialized") is not False
    ):
        raise DevelopmentRuntimePatchError(
            "Published E0-DLP does not adopt the exact seed-1729 manifest"
        )
    return {
        "manifest_path": SEED_MANIFEST_PATH.as_posix(),
        "manifest_bytes": expected_manifest_bytes,
        "manifest_sha256": expected_manifest_sha256,
        "historical_source_records": {
            "generating_script": dict(HISTORICAL_ANFIS_SCRIPT_RECORD),
            "strict_anfis_state_adapter": dict(
                HISTORICAL_ANFIS_DEPENDENCY_RECORD
            ),
            "runtime_lock_validator": dict(HISTORICAL_RUNTIME_VALIDATOR_RECORD),
        },
        "historical_uppercase_artifact_paths": True,
        "patch_lock_path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "base_seed": ADOPTED_BASE_SEED,
        "compatibility_fallback": False,
    }


def collect_patch_prelock_state(
    *,
    base_lock_path: Path = DEFAULT_LOCK_PATH,
    base_lock_schema: Path = DEFAULT_LOCK_SCHEMA,
    runtime_config: Path = DEFAULT_RUNTIME_CONFIG,
    runtime_schema: Path = DEFAULT_RUNTIME_SCHEMA,
    device: str = "cpu",
    verify_parent_remote_publication: bool,
) -> dict[str, Any]:
    """Collect the outcome-free, post-fit E0-DLP parent snapshot."""
    if device != "cpu":
        raise DevelopmentRuntimePatchError("E0-DLP is locked to CPU")
    repository = _require_clean_repository()
    repository["records_verified_at_execution_head"] = True
    patch_head = str(repository["head"])
    publication = _parent_publication(
        patch_head, verify_remote=verify_parent_remote_publication
    )
    base = _base_lock_snapshot(base_lock_path, base_lock_schema)
    _require_ancestor(str(base["lock_commit"]), patch_head)
    base_payload = cast(Mapping[str, Any], base["payload"])
    base_physical = _validate_base_physical_authority(
        base,
        runtime_config=runtime_config,
        runtime_schema=runtime_schema,
        require_physical_artifacts=True,
    )
    runtime = cast(Mapping[str, Any], base_physical["runtime"])
    drift = _base_component_drift(base_payload, patch_head)
    patch_components = _patch_components_record(patch_head)
    publication_sequence = _publication_sequence(str(base["lock_commit"]), patch_head)
    diff = cast(Mapping[str, Any], publication_sequence["base_to_patch"])
    seed_bundle = adopted_seed_bundle_record(
        base,
        require_physical_artifacts=True,
    )
    environment = environment_payload(device, runtime)
    return {
        "runtime": runtime,
        "base_e0_dl": {key: value for key, value in base.items() if key != "payload"},
        "base_payload": base_payload,
        "patch_repository": repository,
        "patch_parent_publication": publication,
        "publication_sequence": publication_sequence,
        "base_component_drift": drift,
        "patch_components": patch_components,
        "git_diff": diff,
        "compatibility_corrections": compatibility_correction_records(),
        "adopted_seed_bundle": seed_bundle,
        "environment": environment,
    }


def build_development_runtime_patch_lock_payload(
    prelock: Mapping[str, Any],
    *,
    full_type_check: Mapping[str, Any],
    focused_tests: Mapping[str, Any],
    dvc_remote_verification: Mapping[str, Any],
    created_at_utc: str,
) -> dict[str, Any]:
    return {
        "lock_version": PATCH_LOCK_VERSION,
        "status": PATCH_STATUS,
        "gate": PATCH_GATE,
        "experiment_id": EXPERIMENT_ID,
        "patch_id": PATCH_ID,
        "created_at_utc": created_at_utc,
        "base_e0_dl": prelock["base_e0_dl"],
        "patch_repository": prelock["patch_repository"],
        "patch_parent_publication": prelock["patch_parent_publication"],
        "publication_sequence": prelock["publication_sequence"],
        "base_component_drift": prelock["base_component_drift"],
        "patch_components": prelock["patch_components"],
        "patch_lock_artifact": patch_lock_artifact_record(),
        "git_diff": prelock["git_diff"],
        "implementation_erratum": dict(PATCH_IMPLEMENTATION_ERRATUM),
        "compatibility_corrections": prelock["compatibility_corrections"],
        "adopted_seed_bundle": prelock["adopted_seed_bundle"],
        "environment": prelock["environment"],
        "dvc_remote_verification": dict(dvc_remote_verification),
        "verification": {
            "full_type_check": dict(full_type_check),
            "focused_tests": dict(focused_tests),
        },
        "audits": dict(PATCH_AUDITS),
        "authorizations": dict(PATCH_AUTHORIZATIONS),
        "seals": dict(PATCH_SEALS),
    }


def _validate_base_models_tree_identity(
    base_entries: Sequence[Mapping[str, Any]],
) -> None:
    canonical_tree = _dvc_tree_bytes(base_entries)
    directory_md5 = (
        hashlib.md5(canonical_tree, usedforsecurity=False).hexdigest() + ".dir"
    )
    if (
        len(base_entries) != EXPECTED_BASE_MODELS_OWNER_NFILES
        or len(canonical_tree) != EXPECTED_BASE_MODELS_TREE_BYTES
        or directory_md5 != EXPECTED_BASE_MODELS_OWNER_MD5
        or _sha256_bytes(canonical_tree) != EXPECTED_BASE_MODELS_TREE_SHA256
    ):
        raise DevelopmentRuntimePatchError(
            "E0-DLP reconstructed base models tree identity drifted"
        )


def _validate_models_owner_payload(owner: Mapping[str, Any]) -> None:
    """Validate all self-contained DVC tree and adoption-delta invariants."""
    expected_keys = {
        "path",
        "role",
        "bytes",
        "sha256",
        "owner_strategy",
        "owned_path",
        "hash_name",
        "hash_value",
        "size",
        "nfiles",
        "checkpoint_paths",
        "tree_bytes",
        "tree_cache_sha256",
        "tree_entry_count",
        "tree_entries_sha256",
        "tree_entries",
        "base_owner_hash_value",
        "base_owner_size",
        "base_owner_nfiles",
        "base_tree_cache_sha256",
        "base_tree_entries_sha256",
        "adoption_delta_count",
        "adoption_delta_records",
        "adoption_delta_records_sha256",
        "base_tree_preserved_exactly",
        "adoption_delta_exactly_seed_checkpoints",
        "directory_payload_verified",
        "checkpoint_membership_verified",
        "pointer_metadata_verified",
    }
    if set(owner) != expected_keys:
        raise DevelopmentRuntimePatchError("E0-DLP models owner fields drifted")
    raw_entries = owner.get("tree_entries")
    if not isinstance(raw_entries, Sequence) or isinstance(raw_entries, (str, bytes)):
        raise DevelopmentRuntimePatchError("E0-DLP models tree entries are invalid")
    entries = [dict(cast(Mapping[str, Any], entry)) for entry in raw_entries]
    relpaths = [str(entry.get("relpath", "")) for entry in entries]
    canonical_tree = _dvc_tree_bytes(entries)
    canonical_tree_md5 = (
        hashlib.md5(canonical_tree, usedforsecurity=False).hexdigest() + ".dir"
    )
    if (
        len(entries) != EXPECTED_ADOPTED_MODELS_OWNER_NFILES
        or owner.get("tree_entry_count") != len(entries)
        or relpaths != sorted(relpaths)
        or len(set(relpaths)) != len(relpaths)
        or owner.get("tree_entries_sha256") != _record_digest(entries)
        or owner.get("hash_value") != canonical_tree_md5
        or owner.get("tree_bytes") != len(canonical_tree)
        or owner.get("tree_cache_sha256") != _sha256_bytes(canonical_tree)
    ):
        raise DevelopmentRuntimePatchError("E0-DLP models tree inventory drifted")

    expected_delta_records: list[dict[str, Any]] = []
    expected_delta_relpaths: set[str] = set()
    entry_by_path = {str(entry["relpath"]): str(entry["md5"]) for entry in entries}
    for checkpoint in SEED_CHECKPOINT_PATHS:
        full_path = checkpoint.as_posix()
        relpath = checkpoint.relative_to("models").as_posix()
        expected_bytes, expected_sha256 = EXPECTED_SEED_FINALS[full_path]
        expected_md5 = SEED_CHECKPOINT_MD5[full_path]
        expected_delta_relpaths.add(relpath)
        expected_delta_records.append(
            {
                "path": full_path,
                "bytes": expected_bytes,
                "sha256": expected_sha256,
                "md5": expected_md5,
            }
        )
        if entry_by_path.get(relpath) != expected_md5:
            raise DevelopmentRuntimePatchError(
                f"E0-DLP models tree lacks the exact checkpoint: {full_path}"
            )

    base_entries = [
        entry for entry in entries if str(entry["relpath"]) not in expected_delta_relpaths
    ]
    _validate_base_models_tree_identity(base_entries)
    expected_static_fields = {
        "path": MODELS_OWNER_PATH.as_posix(),
        "role": "anfis_models_dvc_owner",
        "owner_strategy": "monolithic_parent",
        "owned_path": "models",
        "hash_name": "md5",
        "size": EXPECTED_ADOPTED_MODELS_OWNER_SIZE,
        "nfiles": EXPECTED_ADOPTED_MODELS_OWNER_NFILES,
        "checkpoint_paths": [path.as_posix() for path in SEED_CHECKPOINT_PATHS],
        "base_owner_hash_value": EXPECTED_BASE_MODELS_OWNER_MD5,
        "base_owner_size": EXPECTED_BASE_MODELS_OWNER_SIZE,
        "base_owner_nfiles": EXPECTED_BASE_MODELS_OWNER_NFILES,
        "base_tree_cache_sha256": EXPECTED_BASE_MODELS_TREE_SHA256,
        "base_tree_entries_sha256": _record_digest(base_entries),
        "adoption_delta_count": len(expected_delta_records),
        "adoption_delta_records": expected_delta_records,
        "adoption_delta_records_sha256": _record_digest(expected_delta_records),
        "base_tree_preserved_exactly": True,
        "adoption_delta_exactly_seed_checkpoints": True,
        "directory_payload_verified": True,
        "checkpoint_membership_verified": True,
        "pointer_metadata_verified": True,
    }
    if (
        len(base_entries) != EXPECTED_BASE_MODELS_OWNER_NFILES
        or any(owner.get(key) != value for key, value in expected_static_fields.items())
    ):
        raise DevelopmentRuntimePatchError("E0-DLP models adoption anchors drifted")


def _validate_git_diff_payload(
    record: Mapping[str, Any],
    *,
    base_commit: str,
    patch_head: str,
    paths: Sequence[str],
    modified_paths: frozenset[str],
) -> None:
    expected_entries = [
        {"status": "M" if path in modified_paths else "A", "path": path}
        for path in paths
    ]
    if dict(record) != {
        "base_commit": base_commit,
        "patch_head": patch_head,
        "entries": expected_entries,
        "paths": list(paths),
        "paths_sha256": _path_digest(paths),
        "only_allowed_additions_and_modifications": True,
    }:
        raise DevelopmentRuntimePatchError("E0-DLP publication diff payload drifted")


def _validate_publication_sequence_payload(payload: Mapping[str, Any]) -> None:
    patch_head = str(cast(Mapping[str, Any], payload["patch_repository"])["head"])
    sequence = cast(Mapping[str, Any], payload["publication_sequence"])
    adoption_head = str(sequence.get("adoption_head", ""))
    activation_head = str(sequence.get("activation_head", ""))
    if (
        sequence.get("base_commit") != EXPECTED_BASE_LOCK_COMMIT
        or adoption_head != EXPECTED_ADOPTION_HEAD
        or activation_head != EXPECTED_ACTIVATION_HEAD
        or sequence.get("patch_head") != patch_head
        or sequence.get("adoption_is_direct_first_parent_of_activation") is not True
        or sequence.get("activation_is_direct_first_parent_of_patch") is not True
        or sequence.get("base_is_ancestor_of_adoption") is not True
        or sequence.get("adoption_is_ancestor_of_activation") is not True
        or sequence.get("activation_is_ancestor_of_patch") is not True
    ):
        raise DevelopmentRuntimePatchError("E0-DLP publication chronology drifted")
    _validate_git_diff_payload(
        cast(Mapping[str, Any], sequence["base_to_adoption"]),
        base_commit=EXPECTED_BASE_LOCK_COMMIT,
        patch_head=adoption_head,
        paths=PATCH_ADOPTION_DIFF_ALLOWLIST,
        modified_paths=frozenset(
            {
                "src/experiments/build_closure_pipe_sequences.py",
                "tests/test_build_closure_pipe_sequences.py",
                MODELS_OWNER_PATH.as_posix(),
            }
        ),
    )
    _validate_git_diff_payload(
        cast(Mapping[str, Any], sequence["adoption_to_activation"]),
        base_commit=adoption_head,
        patch_head=activation_head,
        paths=PATCH_ACTIVATION_PATHS,
        modified_paths=frozenset(PATCH_ACTIVATION_PATHS),
    )
    _validate_git_diff_payload(
        cast(Mapping[str, Any], sequence["activation_to_patch"]),
        base_commit=activation_head,
        patch_head=patch_head,
        paths=PATCH_REPAIR_PATHS,
        modified_paths=frozenset(PATCH_REPAIR_PATHS),
    )
    _validate_git_diff_payload(
        cast(Mapping[str, Any], sequence["base_to_patch"]),
        base_commit=EXPECTED_BASE_LOCK_COMMIT,
        patch_head=patch_head,
        paths=PATCH_PARENT_DIFF_ALLOWLIST,
        modified_paths=frozenset(
            {*BASE_COMPONENT_DRIFT_ALLOWLIST, MODELS_OWNER_PATH.as_posix()}
        ),
    )
    if payload.get("git_diff") != sequence["base_to_patch"]:
        raise DevelopmentRuntimePatchError("E0-DLP aggregate publication diff drifted")


def validate_development_runtime_patch_lock_payload(
    payload: Mapping[str, Any], schema: Mapping[str, Any]
) -> None:
    try:
        validate_json_schema(payload, schema, instance_path="$.development_runtime_patch_lock")
    except ClosureContractError as exc:
        raise DevelopmentRuntimePatchError(str(exc)) from exc
    if payload.get("lock_version") != PATCH_LOCK_VERSION:
        raise DevelopmentRuntimePatchError("E0-DLP lock version drifted")
    if payload.get("authorizations") != PATCH_AUTHORIZATIONS:
        raise DevelopmentRuntimePatchError("E0-DLP authorizations drifted")
    if payload.get("seals") != PATCH_SEALS:
        raise DevelopmentRuntimePatchError("E0-DLP seals drifted")
    if payload.get("audits") != PATCH_AUDITS:
        raise DevelopmentRuntimePatchError("E0-DLP audit seals drifted")
    if payload.get("implementation_erratum") != PATCH_IMPLEMENTATION_ERRATUM:
        raise DevelopmentRuntimePatchError("E0-DLP implementation erratum drifted")
    if payload.get("compatibility_corrections") != compatibility_correction_records():
        raise DevelopmentRuntimePatchError("E0-DLP compatibility corrections drifted")
    if payload.get("patch_lock_artifact") != patch_lock_artifact_record():
        raise DevelopmentRuntimePatchError("E0-DLP patch-lock artifact record drifted")
    _validate_publication_sequence_payload(payload)
    created = payload.get("created_at_utc")
    if not isinstance(created, str):
        raise DevelopmentRuntimePatchError("E0-DLP created_at_utc is invalid")
    try:
        timestamp = datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DevelopmentRuntimePatchError("E0-DLP created_at_utc is invalid") from exc
    if timestamp.utcoffset() is None:
        raise DevelopmentRuntimePatchError("E0-DLP created_at_utc requires a timezone")
    drift = cast(Mapping[str, Any], payload.get("base_component_drift"))
    drift_records = cast(Sequence[Mapping[str, Any]], drift.get("records"))
    if (
        drift.get("count") != len(BASE_COMPONENT_DRIFT_ALLOWLIST)
        or drift.get("allowlist") != sorted(BASE_COMPONENT_DRIFT_ALLOWLIST)
        or drift.get("observed_paths") != sorted(BASE_COMPONENT_DRIFT_ALLOWLIST)
        or [str(record.get("path", "")) for record in drift_records]
        != sorted(BASE_COMPONENT_DRIFT_ALLOWLIST)
        or drift.get("records_sha256") != _record_digest(drift_records)
        or drift.get("only_allowlisted_base_components_changed") is not True
    ):
        raise DevelopmentRuntimePatchError("E0-DLP base component allowlist drifted")
    components = payload.get("patch_components")
    if not isinstance(components, Mapping):
        raise DevelopmentRuntimePatchError("E0-DLP patch components are invalid")
    component_records = components.get("records")
    component_paths = sorted(PATCH_COMPONENT_ROLES)
    if (
        components.get("count") != len(component_paths)
        or components.get("paths") != component_paths
        or components.get("paths_sha256") != _path_digest(component_paths)
        or not isinstance(component_records, Sequence)
        or isinstance(component_records, (str, bytes))
        or [
            record.get("path")
            for record in component_records
            if isinstance(record, Mapping)
        ]
        != component_paths
        or components.get("records_sha256")
        != _record_digest(cast(Sequence[Mapping[str, Any]], component_records))
    ):
        raise DevelopmentRuntimePatchError("E0-DLP patch component paths drifted")
    diff = cast(Mapping[str, Any], payload.get("git_diff"))
    if diff.get("paths") != list(PATCH_PARENT_DIFF_ALLOWLIST):
        raise DevelopmentRuntimePatchError("E0-DLP Git diff allowlist drifted")
    bundle = cast(Mapping[str, Any], payload.get("adopted_seed_bundle"))
    if (
        bundle.get("base_seed") != ADOPTED_BASE_SEED
        or bundle.get("status") != "adopted_prepatch_artifact_without_rematerialization"
        or bundle.get("original_manifest_mutated") is not False
        or bundle.get("original_seed_rematerialized") is not False
        or bundle.get("future_outcomes_accessed") is not False
        or bundle.get("evaluation_authorized") is not False
        or bundle.get("e0_u_authorized") is not False
    ):
        raise DevelopmentRuntimePatchError("E0-DLP adopted seed dialect drifted")
    manifest_record = cast(Mapping[str, Any], bundle.get("manifest"))
    expected_manifest = EXPECTED_SEED_FINALS[SEED_MANIFEST_PATH.as_posix()]
    if (
        manifest_record.get("path") != SEED_MANIFEST_PATH.as_posix()
        or manifest_record.get("role") != "seed_1729_completion_manifest"
        or manifest_record.get("bytes") != expected_manifest[0]
        or manifest_record.get("sha256") != expected_manifest[1]
        or bundle.get("bundle_record_count") != 13
        or bundle.get("physical_final_count") != 14
        or bundle.get("temporary_or_partial_file_count") != 0
    ):
        raise DevelopmentRuntimePatchError("E0-DLP adopted seed anchors drifted")
    locked_output_records = [
        cast(Mapping[str, Any], bundle.get("state")),
        *cast(Sequence[Mapping[str, Any]], bundle.get("checkpoints")),
        *cast(Sequence[Mapping[str, Any]], bundle.get("lightweight_outputs")),
    ]
    if len(locked_output_records) != 13:
        raise DevelopmentRuntimePatchError("E0-DLP adopted seed output count drifted")
    if {str(record.get("path", "")) for record in locked_output_records} != set(
        EXPECTED_SEED_OUTPUT_METADATA
    ):
        raise DevelopmentRuntimePatchError("E0-DLP adopted seed output path set drifted")
    for record in locked_output_records:
        path = str(record.get("path", ""))
        expected = EXPECTED_SEED_FINALS.get(path)
        metadata = EXPECTED_SEED_OUTPUT_METADATA.get(path)
        if (
            expected is None
            or metadata is None
            or record.get("bytes") != expected[0]
            or record.get("sha256") != expected[1]
            or record.get("role") != metadata["role"]
            or record.get("module") != metadata.get("module")
        ):
            raise DevelopmentRuntimePatchError(
                f"E0-DLP adopted seed output anchor drifted: {path}"
            )
    expected_bundle_records = [
        dict(manifest_record),
        *sorted(
            [dict(record) for record in locked_output_records],
            key=lambda record: str(record["path"]),
        ),
    ]
    if bundle.get("bundle_records_sha256") != _record_digest(expected_bundle_records):
        raise DevelopmentRuntimePatchError("E0-DLP adopted seed record digest drifted")
    state = cast(Mapping[str, Any], bundle["state"])
    dvc = cast(Mapping[str, Any], bundle.get("dvc"))
    state_pointer = cast(Mapping[str, Any], dvc.get("state_pointer"))
    models_owner = cast(Mapping[str, Any], dvc.get("models_owner"))
    if (
        set(dvc) != {"state_pointer", "models_owner", "registered"}
        or set(state_pointer)
        != {
            "path",
            "role",
            "bytes",
            "sha256",
            "owner_strategy",
            "hash_name",
            "hash_value",
            "size",
            "payload_verified",
        }
        or dvc.get("registered") is not True
        or state_pointer.get("path") != SEED_STATE_POINTER_PATH.as_posix()
        or state_pointer.get("role") != "adaptive_state_dvc_pointer"
        or state_pointer.get("owner_strategy") != "explicit_pointer"
        or state_pointer.get("hash_name") != "md5"
        or state_pointer.get("hash_value") != EXPECTED_SEED_STATE_MD5
        or state_pointer.get("size") != state.get("bytes")
        or state_pointer.get("payload_verified") is not True
    ):
        raise DevelopmentRuntimePatchError("E0-DLP state DVC ownership drifted")
    _validate_models_owner_payload(models_owner)
    completion_order_evidence = bundle.get("completion_order_evidence")
    if not isinstance(completion_order_evidence, Mapping) or dict(
        completion_order_evidence
    ) != _completion_order_evidence_record(
        bundle_records_sha256=str(bundle["bundle_records_sha256"]),
        models_owner_hash_value=str(models_owner["hash_value"]),
    ):
        raise DevelopmentRuntimePatchError(
            "E0-DLP content-addressed completion-order evidence drifted"
        )
    expected_original_authorization = {
        "lock_path": DEFAULT_LOCK_PATH.as_posix(),
        "lock_sha256": EXPECTED_BASE_LOCK_SHA256,
        "execution_head": EXPECTED_BASE_LOCK_COMMIT,
        "published_ref": EXPECTED_PUBLISHED_REF,
        "published_head": EXPECTED_BASE_LOCK_COMMIT,
        "remote_main_oid": EXPECTED_BASE_LOCK_COMMIT,
    }
    if bundle.get("original_authorization") != expected_original_authorization:
        raise DevelopmentRuntimePatchError("E0-DLP original authorization drifted")
    remote_evidence = cast(Mapping[str, Any], payload.get("dvc_remote_verification"))
    expected_remote_targets = [
        {
            "artifact_role": "adaptive_state",
            "pointer_path": state_pointer["path"],
            "pointer_sha256": state_pointer["sha256"],
            "hash_name": state_pointer["hash_name"],
            "hash_value": state_pointer["hash_value"],
            "size": state_pointer["size"],
        },
        {
            "artifact_role": "anfis_models",
            "pointer_path": models_owner["path"],
            "pointer_sha256": models_owner["sha256"],
            "hash_name": models_owner["hash_name"],
            "hash_value": models_owner["hash_value"],
            "size": models_owner["size"],
            "nfiles": models_owner["nfiles"],
            "tree_cache_sha256": models_owner["tree_cache_sha256"],
            "tree_entries_sha256": models_owner["tree_entries_sha256"],
        },
    ]
    if remote_evidence.get("targets") != expected_remote_targets:
        raise DevelopmentRuntimePatchError("E0-DLP DVC target evidence drifted")
    state_audit = cast(Mapping[str, Any], bundle.get("state_audit"))
    if (
        state_audit.get("rows") != 42_110
        or state_audit.get("locations") != 353
        or state_audit.get("minimum_year_month") != "2000-01"
        or state_audit.get("maximum_year_month") != "2021-12"
        or state_audit.get("role_counts")
        != {
            "training": 36_639,
            "model_selection": 3_739,
            "calibration_threshold": 1_732,
        }
        or state_audit.get("delta_previous_month_missing_count") != 8_041
        or state_audit.get("output_allowlist") != list(STATE_ALLOWLIST)
    ):
        raise DevelopmentRuntimePatchError("E0-DLP seed state audit anchors drifted")
    verification = cast(Mapping[str, Any], payload.get("verification"))
    for field, command in (
        ("full_type_check", PATCH_TYPE_CHECK_COMMAND),
        ("focused_tests", PATCH_FOCUSED_TEST_COMMAND),
    ):
        evidence = cast(Mapping[str, Any], verification.get(field))
        expected_keys = {
            "command",
            "exit_code",
            "stdout_sha256",
            "stderr_sha256",
            "passed",
        }
        if field == "focused_tests":
            expected_keys.update({"environment", "test_count"})
        if (
            set(evidence) != expected_keys
            or tuple(evidence["command"]) != command
            or evidence.get("exit_code") != 0
            or evidence.get("passed") is not True
            or SHA256_RE.fullmatch(str(evidence.get("stdout_sha256", ""))) is None
            or SHA256_RE.fullmatch(str(evidence.get("stderr_sha256", ""))) is None
        ):
            raise DevelopmentRuntimePatchError(f"E0-DLP {field} evidence drifted")
        if field == "focused_tests" and (
            evidence.get("environment") != PATCH_TEST_ENVIRONMENT
            or evidence.get("test_count") != PATCH_FOCUSED_TEST_COUNT
        ):
            raise DevelopmentRuntimePatchError(
                "E0-DLP focused_tests execution evidence drifted"
            )


def patch_dvc_remote_push_command(
    runtime: Mapping[str, Any], bundle: Mapping[str, Any]
) -> tuple[str, ...]:
    """Return the one exact E0-DLP two-target DVC verification command."""
    dvc = cast(Mapping[str, Any], bundle["dvc"])
    state_pointer = cast(Mapping[str, Any], dvc["state_pointer"])
    models_owner = cast(Mapping[str, Any], dvc["models_owner"])
    return (
        DVC_EXECUTABLE,
        "push",
        "-j",
        "1",
        "-r",
        _dvc_remote_name(runtime),
        str(state_pointer["path"]),
        str(models_owner["path"]),
    )


def _normalized_patch_dvc_push_result(
    stdout: bytes, stderr: bytes, returncode: int
) -> str:
    if returncode != 0:
        return "failed"
    output = (stdout + b"\n" + stderr).decode("utf-8", errors="replace")
    output = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", output)
    lines = [line.strip().lower() for line in output.splitlines() if line.strip()]
    if any(re.fullmatch(r"[1-9][0-9]* (?:file|files) pushed", line) for line in lines):
        return "objects_uploaded"
    if lines == ["everything is up to date."]:
        return "everything_up_to_date"
    return "unexpected_success_output"


def _require_fixed_dvc_executable(command: Sequence[str]) -> None:
    if not command or command[0] != DVC_EXECUTABLE:
        raise DevelopmentRuntimePatchError(
            "E0-DLP DVC command must use the fixed repository executable"
        )
    executable = _lexical_repository_path(command[0])
    try:
        executable_metadata = executable.lstat()
    except FileNotFoundError as exc:
        raise DevelopmentRuntimePatchError(
            f"Fixed E0-DLP DVC executable is absent: {command[0]}"
        ) from exc
    if (
        not stat.S_ISREG(executable_metadata.st_mode)
        or not os.access(executable, os.X_OK)
    ):
        raise DevelopmentRuntimePatchError(
            f"Fixed E0-DLP DVC executable is not a regular executable: {command[0]}"
        )


def verify_patch_dvc_remote_by_idempotent_push(
    runtime: Mapping[str, Any], bundle: Mapping[str, Any]
) -> dict[str, Any]:
    """Require two already-synchronized pushes for the adopted seed bundle."""
    command = patch_dvc_remote_push_command(runtime, bundle)
    _require_fixed_dvc_executable(command)
    environment = os.environ.copy()
    for key in tuple(environment):
        if key.startswith("DVC_"):
            environment.pop(key)
    environment.update(DVC_REMOTE_ENVIRONMENT)
    attempts: list[dict[str, Any]] = []
    for attempt in (1, 2):
        try:
            result = subprocess.run(
                list(command),
                cwd=PROJECT_ROOT,
                check=False,
                capture_output=True,
                text=False,
                env=environment,
                timeout=600,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DevelopmentRuntimePatchError(
                "Targeted E0-DLP DVC verification could not complete"
            ) from exc
        attempts.append(
            {
                "attempt": attempt,
                "exit_code": result.returncode,
                "stdout_sha256": _sha256_bytes(result.stdout),
                "stderr_sha256": _sha256_bytes(result.stderr),
                "normalized_result": _normalized_patch_dvc_push_result(
                    result.stdout,
                    result.stderr,
                    result.returncode,
                ),
            }
        )

    dvc = cast(Mapping[str, Any], bundle["dvc"])
    state_pointer = cast(Mapping[str, Any], dvc["state_pointer"])
    models_owner = cast(Mapping[str, Any], dvc["models_owner"])
    targets = [
        {
            "artifact_role": "adaptive_state",
            "pointer_path": state_pointer["path"],
            "pointer_sha256": state_pointer["sha256"],
            "hash_name": state_pointer["hash_name"],
            "hash_value": state_pointer["hash_value"],
            "size": state_pointer["size"],
        },
        {
            "artifact_role": "anfis_models",
            "pointer_path": models_owner["path"],
            "pointer_sha256": models_owner["sha256"],
            "hash_name": models_owner["hash_name"],
            "hash_value": models_owner["hash_value"],
            "size": models_owner["size"],
            "nfiles": models_owner["nfiles"],
            "tree_cache_sha256": models_owner["tree_cache_sha256"],
            "tree_entries_sha256": models_owner["tree_entries_sha256"],
        },
    ]
    evidence = {
        "method": DVC_REMOTE_VERIFICATION_METHOD,
        "command": list(command),
        "environment": dict(DVC_REMOTE_ENVIRONMENT),
        **_dvc_remote_configuration_fingerprint(_dvc_remote_name(runtime)),
        "targets": targets,
        "attempts": attempts,
        "dvc_remote_verified_at_patch": all(
            item["exit_code"] == 0
            and item["normalized_result"] == "everything_up_to_date"
            for item in attempts
        ),
    }
    if evidence["dvc_remote_verified_at_patch"] is not True:
        raise DevelopmentRuntimePatchError(
            "E0-DLP requires two already-up-to-date targeted DVC pushes"
        )
    _validate_dvc_remote_evidence(
        evidence,
        bundle,
        runtime=runtime,
        verify_current_remote_config=True,
    )
    return evidence


def _validate_dvc_remote_evidence(
    evidence: Mapping[str, Any],
    bundle: Mapping[str, Any],
    *,
    runtime: Mapping[str, Any],
    verify_current_remote_config: bool,
) -> None:
    dvc = cast(Mapping[str, Any], bundle["dvc"])
    state_pointer = cast(Mapping[str, Any], dvc["state_pointer"])
    models_owner = cast(Mapping[str, Any], dvc["models_owner"])
    expected_targets = [
        {
            "artifact_role": "adaptive_state",
            "pointer_path": state_pointer["path"],
            "pointer_sha256": state_pointer["sha256"],
            "hash_name": state_pointer["hash_name"],
            "hash_value": state_pointer["hash_value"],
            "size": state_pointer["size"],
        },
        {
            "artifact_role": "anfis_models",
            "pointer_path": models_owner["path"],
            "pointer_sha256": models_owner["sha256"],
            "hash_name": models_owner["hash_name"],
            "hash_value": models_owner["hash_value"],
            "size": models_owner["size"],
            "nfiles": models_owner["nfiles"],
            "tree_cache_sha256": models_owner["tree_cache_sha256"],
            "tree_entries_sha256": models_owner["tree_entries_sha256"],
        },
    ]
    remote_name = _dvc_remote_name(runtime)
    expected_command = list(patch_dvc_remote_push_command(runtime, bundle))
    if (
        evidence.get("method") != DVC_REMOTE_VERIFICATION_METHOD
        or evidence.get("command") != expected_command
        or evidence.get("environment") != DVC_REMOTE_ENVIRONMENT
        or evidence.get("remote_name") != remote_name
        or evidence.get("targets") != expected_targets
        or evidence.get("dvc_remote_verified_at_patch") is not True
    ):
        raise DevelopmentRuntimePatchError("E0-DLP DVC remote evidence drifted")
    remote_url_sha256 = evidence.get("remote_url_sha256")
    if not isinstance(remote_url_sha256, str) or SHA256_RE.fullmatch(remote_url_sha256) is None:
        raise DevelopmentRuntimePatchError("E0-DLP DVC remote fingerprint is invalid")
    if verify_current_remote_config:
        current = _dvc_remote_configuration_fingerprint(remote_name)
        if dict(current) != {
            "remote_name": remote_name,
            "remote_url_sha256": remote_url_sha256,
        }:
            raise DevelopmentRuntimePatchError(
                "Current DVC remote fingerprint differs from E0-DLP"
            )
    attempts = evidence.get("attempts")
    if not isinstance(attempts, Sequence) or isinstance(attempts, (str, bytes)) or len(attempts) != 2:
        raise DevelopmentRuntimePatchError("E0-DLP requires two DVC verification attempts")
    for index, raw_attempt in enumerate(attempts, start=1):
        if not isinstance(raw_attempt, Mapping):
            raise DevelopmentRuntimePatchError("E0-DLP DVC verification attempt drifted")
        attempt = cast(Mapping[str, Any], raw_attempt)
        if (
            attempt.get("attempt") != index
            or attempt.get("exit_code") != 0
            or attempt.get("normalized_result") != "everything_up_to_date"
            or SHA256_RE.fullmatch(str(attempt.get("stdout_sha256", ""))) is None
            or SHA256_RE.fullmatch(str(attempt.get("stderr_sha256", ""))) is None
        ):
            raise DevelopmentRuntimePatchError("E0-DLP DVC verification attempt drifted")


def _require_patch_published(
    patch_lock_path: Path, *, verify_remote: bool
) -> tuple[str, str, str, str, str | None]:
    relative = _relative(patch_lock_path)
    companion_relative = DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix()
    status = _git(
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        relative,
        companion_relative,
    )
    if status:
        raise DevelopmentRuntimePatchError(f"E0-DLP publication bundle is modified: {status}")
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    physical = _read_regular_repository_bytes(
        patch_lock_path,
        context="Physical E0-DLP lock",
    )
    _read_regular_repository_bytes(
        DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        context="Physical E0-DLP companion",
    )
    committed = _git_blob(execution_head, relative)
    if committed != physical:
        raise DevelopmentRuntimePatchError("E0-DLP lock must be committed unchanged in HEAD")
    published_head = _require_commit(_git("rev-parse", EXPECTED_PUBLISHED_REF), context="origin/main")
    published = _git_blob(published_head, relative)
    if published != physical:
        raise DevelopmentRuntimePatchError("E0-DLP lock must be published unchanged on origin/main")
    remote_oid = _remote_main_oid() if verify_remote else None
    if remote_oid is not None and remote_oid != published_head:
        raise DevelopmentRuntimePatchError("Local and real origin/main differ for E0-DLP")
    _require_ancestor(published_head, execution_head)
    return relative, execution_head, EXPECTED_PUBLISHED_REF, published_head, remote_oid


def _validate_patch_publication_bundle(
    payload: Mapping[str, Any], *, execution_head: str, published_head: str
) -> str:
    """Require one direct P-DLP commit containing only the lock and companion."""
    lock_path = DEFAULT_PATCH_LOCK_PATH.as_posix()
    companion_path = DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix()
    lock_commit = _introduced_commit(lock_path)
    companion_commit = _introduced_commit(companion_path)
    if lock_commit != companion_commit:
        raise DevelopmentRuntimePatchError(
            "E0-DLP lock and companion must be introduced by the same commit"
        )
    patch_head = str(cast(Mapping[str, Any], payload["patch_repository"])["head"])
    ancestry = _git("rev-list", "--parents", "-n", "1", lock_commit).split()
    if ancestry != [lock_commit, patch_head]:
        raise DevelopmentRuntimePatchError(
            "P-DLP must be a direct non-merge child of R-DLP"
        )
    expected_publication_paths = tuple(sorted((lock_path, companion_path)))
    _git_diff_exact(
        patch_head,
        lock_commit,
        expected_paths=expected_publication_paths,
        expected_modified_paths=frozenset(),
    )
    _require_ancestor(lock_commit, published_head)
    _require_ancestor(lock_commit, execution_head)
    for descendant, context in (
        (published_head, "origin/main"),
        (execution_head, "execution HEAD"),
    ):
        touched = _git(
            "rev-list",
            "--full-history",
            f"{lock_commit}..{descendant}",
            "--",
            lock_path,
            companion_path,
        )
        if touched:
            raise DevelopmentRuntimePatchError(
                f"E0-DLP lock bundle was touched after P-DLP on {context}"
            )

    lock_blob = _git_blob(lock_commit, lock_path)
    companion_blob = _git_blob(lock_commit, companion_path)
    if lock_blob is None or companion_blob is None:
        raise DevelopmentRuntimePatchError("P-DLP lock bundle is incomplete")
    physical_lock = _read_regular_repository_bytes(
        lock_path,
        context="Physical E0-DLP lock",
    )
    physical_companion = _read_regular_repository_bytes(
        companion_path,
        context="Physical E0-DLP companion",
    )
    if (
        lock_blob != physical_lock
        or _git_blob(execution_head, lock_path) != physical_lock
        or _git_blob(published_head, lock_path) != physical_lock
        or _git_blob(execution_head, companion_path) != physical_companion
        or _git_blob(published_head, companion_path) != physical_companion
        or companion_blob != physical_companion
    ):
        raise DevelopmentRuntimePatchError(
            "E0-DLP companion must remain unchanged in P, origin/main, HEAD, and the worktree"
        )
    companion = _decode_json_mapping_bytes(
        companion_blob,
        context="E0-DLP companion",
    )

    component_records = cast(
        Sequence[Mapping[str, Any]],
        cast(Mapping[str, Any], payload["patch_components"])["records"],
    )
    component_by_path = {str(record["path"]): record for record in component_records}
    locker = component_by_path[
        "src/experiments/lock_closure_development_runtime_patch.py"
    ]
    validator = component_by_path[
        "src/experiments/closure_development_runtime_patch.py"
    ]
    patch_schema = component_by_path[
        "configs/closure_v1/development_runtime_patch_lock.schema.json"
    ]
    base = cast(Mapping[str, Any], payload["base_e0_dl"])
    base_lock = cast(Mapping[str, Any], base["lock"])
    base_schema = cast(Mapping[str, Any], base["schema"])

    def with_role(record: Mapping[str, Any], role: str) -> dict[str, Any]:
        return {
            "path": record["path"],
            "role": role,
            "bytes": record["bytes"],
            "sha256": record["sha256"],
        }

    expected = {
        "manifest_version": "closure_development_runtime_patch_companion_manifest_v1",
        "status": "completed",
        "experiment_id": EXPERIMENT_ID,
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "created_at_utc": payload["created_at_utc"],
        "outputs": [
            {
                "path": lock_path,
                "role": "external_development_runtime_patch_lock",
                "bytes": len(lock_blob),
                "sha256": _sha256_bytes(lock_blob),
            }
        ],
        "script": with_role(locker, "generating_script"),
        "inputs": [
            with_role(base_lock, "base_development_runtime_lock"),
            with_role(base_schema, "base_development_runtime_lock_schema"),
            with_role(patch_schema, "development_runtime_patch_lock_schema"),
            with_role(validator, "development_runtime_patch_validator"),
        ],
        "development_fit_authorized": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
        "authoritative_contract": False,
        "authoritative_lock_path": lock_path,
    }
    if dict(companion) != expected:
        raise DevelopmentRuntimePatchError("E0-DLP companion manifest drifted")
    return lock_commit


def _validate_patch_parent_publication_record(
    record: Mapping[str, Any], patch_head: str
) -> None:
    expected = {
        "tracking_ref": EXPECTED_PUBLISHED_REF,
        "tracking_oid": patch_head,
        "remote_ref": "refs/heads/main",
        "remote_oid": patch_head,
        "published_head": patch_head,
        "execution_head": patch_head,
        "published_head_is_ancestor_of_execution": True,
        "local_tracking_verified": True,
        "remote_verified": True,
    }
    if dict(record) != expected:
        raise DevelopmentRuntimePatchError(
            "E0-DLP historical patch-parent publication record drifted"
        )


def _validate_effective_patch_records_at_execution(
    payload: Mapping[str, Any], execution_head: str
) -> None:
    patch_head = str(cast(Mapping[str, Any], payload["patch_repository"])["head"])
    drift = cast(Mapping[str, Any], payload["base_component_drift"])
    records = cast(Sequence[Mapping[str, Any]], drift["records"])
    for record in records:
        effective = {
            "path": record["path"],
            "role": "patched_base_component",
            "bytes": record["patch_bytes"],
            "sha256": record["patch_sha256"],
        }
        _validate_record_at_head(
            effective,
            execution_head,
            context="effective patched base component",
        )
        _physical_record_matches(
            effective,
            context="effective patched base component",
        )
    patch_components = cast(Mapping[str, Any], payload["patch_components"])
    for record in cast(Sequence[Mapping[str, Any]], patch_components["records"]):
        _validate_record_at_head(
            record,
            execution_head,
            context="effective E0-DLP patch component",
        )
        _physical_record_matches(
            record,
            context="effective E0-DLP patch component",
        )
    bundle = cast(Mapping[str, Any], payload["adopted_seed_bundle"])
    bundle_dvc = cast(Mapping[str, Any], bundle["dvc"])
    immutable_git_records = [
        cast(Mapping[str, Any], bundle["manifest"]),
        *cast(Sequence[Mapping[str, Any]], bundle["lightweight_outputs"]),
        cast(Mapping[str, Any], bundle_dvc["state_pointer"]),
    ]
    for record in immutable_git_records:
        for head, context in (
            (patch_head, "E0-DLP adopted seed Git-at-H"),
            (execution_head, "E0-DLP adopted seed Git-at-execution"),
        ):
            _validate_record_at_head(record, head, context=context)
        physical_record = {
            key: record[key] for key in ("path", "role", "bytes", "sha256")
        }
        _physical_record_matches(
            physical_record,
            context="effective E0-DLP adopted seed record",
        )
    historical_models_owner = cast(Mapping[str, Any], bundle_dvc["models_owner"])
    _validate_record_at_head(
        historical_models_owner,
        patch_head,
        context="historical E0-DLP models.dvc adoption owner",
    )


def _legacy_summary(
    *,
    base: Mapping[str, Any],
    relative_base_lock_path: str,
    execution_head: str,
    published_ref: str | None,
    published_head: str | None,
    remote_main_oid: str | None,
    require_published: bool,
    require_physical_artifacts: bool,
) -> dict[str, Any]:
    base_payload = cast(Mapping[str, Any], base["payload"])
    locked_head = str(base["locked_repository_head"])
    fit_predicates = {
        "payload_authorization_verified": True,
        "locked_parent_published_at_lock": True,
        "physical_artifacts_verified": require_physical_artifacts,
        "publication_verified": require_published,
        "live_git_remote_verified": remote_main_oid is not None,
        "canonical_origin_identity_verified": True,
        "common_origin_output_verified": require_physical_artifacts,
        "expert_state_output_verified": require_physical_artifacts,
        "restored_development_sources_verified": require_physical_artifacts,
        "dvc_remote_verified_at_lock": True,
        "locked_head_is_ancestor": True,
    }
    effective = all(fit_predicates.values())
    planned = cast(Mapping[str, Any], base_payload["planned_artifacts"])
    summary = {
        "lock_path": relative_base_lock_path,
        "lock_sha256": cast(Mapping[str, Any], base["lock"])["sha256"],
        "lock_version": BASE_LOCK_VERSION,
        "status": "locked",
        "locked_repository_head": locked_head,
        "execution_head": execution_head,
        "published_ref": published_ref,
        "published_head": published_head,
        "remote_main_oid": remote_main_oid,
        "locked_head_is_ancestor": True,
        "locked_parent_published_at_lock": True,
        "publication_verified": require_published,
        "tracking_ref_publication_verified": require_published,
        "remote_publication_verified": remote_main_oid is not None,
        "canonical_origin_identity_verified": True,
        "component_count": len(cast(Sequence[Any], base_payload["components"])),
        "planned_artifact_path_count": planned["count"],
        "planned_artifact_paths_sha256": planned["sha256"],
        "device": cast(Mapping[str, Any], base_payload["environment"])["device"],
        "metadata_verified": True,
        "physical_artifacts_required": require_physical_artifacts,
        "physical_artifacts_verified": require_physical_artifacts,
        "common_origin_output_verified": require_physical_artifacts,
        "expert_state_output_verified": require_physical_artifacts,
        "restored_development_sources_verified": require_physical_artifacts,
        "dvc_remote_verified_at_lock": True,
        "dvc_remote_verified": True,
        "fit_authorization_predicates": fit_predicates,
        "payload_development_fit_authorized": True,
        "payload_evaluation_authorized": False,
        "payload_e0_u_authorized": False,
        "development_fit_authorized": effective,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "fit_authorized": effective,
        "future_outcomes_accessed": False,
    }
    if set(summary) != LEGACY_SUMMARY_KEYS:
        raise DevelopmentRuntimePatchError("E0-DLP legacy summary shape drifted")
    return summary


def load_and_validate_development_runtime_patch_lock(
    patch_lock_path: Path = DEFAULT_PATCH_LOCK_PATH,
    patch_lock_schema: Path = DEFAULT_PATCH_LOCK_SCHEMA,
    *,
    base_lock_path: Path = DEFAULT_LOCK_PATH,
    base_lock_schema: Path = DEFAULT_LOCK_SCHEMA,
    runtime_config: Path = DEFAULT_RUNTIME_CONFIG,
    runtime_schema: Path = DEFAULT_RUNTIME_SCHEMA,
    device: str | None = None,
    require_published: bool = True,
    require_physical_artifacts: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate additive E0-DLP and return the exact legacy E0-DL summary."""
    _require_default_validation_paths(
        patch_lock_path=patch_lock_path,
        patch_lock_schema=patch_lock_schema,
        base_lock_path=base_lock_path,
        base_lock_schema=base_lock_schema,
        runtime_config=runtime_config,
        runtime_schema=runtime_schema,
    )
    payload = _load_regular_json_mapping(
        patch_lock_path,
        context="E0-DLP lock",
    )
    schema = _load_regular_json_mapping(
        patch_lock_schema,
        context="E0-DLP lock schema",
    )
    validate_development_runtime_patch_lock_payload(payload, schema)
    base = _base_lock_snapshot(base_lock_path, base_lock_schema)
    expected_base = {key: value for key, value in base.items() if key != "payload"}
    if payload.get("base_e0_dl") != expected_base:
        raise DevelopmentRuntimePatchError("E0-DLP base E0-DL snapshot drifted")
    base_physical = _validate_base_physical_authority(
        base,
        runtime_config=runtime_config,
        runtime_schema=runtime_schema,
        require_physical_artifacts=require_physical_artifacts,
    )
    patch_parent = cast(Mapping[str, Any], payload["patch_repository"])
    patch_head = _require_commit(patch_parent.get("head"), context="E0-DLP patch parent")
    if dict(patch_parent) != {
        "head": patch_head,
        "branch": "main",
        "worktree_status": "clean",
        "dirty_paths": [],
        "records_verified_at_execution_head": True,
    }:
        raise DevelopmentRuntimePatchError("E0-DLP patch repository record drifted")
    _require_ancestor(str(base["lock_commit"]), patch_head)
    _validate_patch_parent_publication_record(
        cast(Mapping[str, Any], payload["patch_parent_publication"]),
        patch_head,
    )
    base_payload = cast(Mapping[str, Any], base["payload"])
    if payload.get("base_component_drift") != _base_component_drift(base_payload, patch_head):
        raise DevelopmentRuntimePatchError("E0-DLP base component drift records changed")
    if payload.get("patch_components") != _patch_components_record(patch_head):
        raise DevelopmentRuntimePatchError("E0-DLP patch component records changed")
    publication_sequence = _publication_sequence(str(base["lock_commit"]), patch_head)
    if payload.get("publication_sequence") != publication_sequence:
        raise DevelopmentRuntimePatchError("E0-DLP A/H/R publication sequence changed")
    if payload.get("git_diff") != publication_sequence["base_to_patch"]:
        raise DevelopmentRuntimePatchError("E0-DLP Git diff changed")
    runtime = cast(Mapping[str, Any], base_physical["runtime"])
    current_execution_head = _require_commit(
        _git("rev-parse", "HEAD"),
        context="execution HEAD",
    )
    locked_bundle = cast(Mapping[str, Any], payload["adopted_seed_bundle"])
    if require_physical_artifacts:
        locked_dvc = cast(Mapping[str, Any], locked_bundle["dvc"])
        locked_models_owner = cast(Mapping[str, Any], locked_dvc["models_owner"])
        _validate_locked_models_owner(locked_models_owner, patch_head=patch_head)
        bundle = adopted_seed_bundle_record(
            base,
            require_physical_artifacts=True,
            locked_models_owner=locked_models_owner,
            execution_head=current_execution_head,
            runtime=runtime,
        )
        if locked_bundle != bundle:
            raise DevelopmentRuntimePatchError("E0-DLP adopted seed bundle changed")
        current_environment = environment_payload("cpu", runtime)
        if payload.get("environment") != current_environment:
            raise DevelopmentRuntimePatchError("E0-DLP execution environment drifted")
    _validate_dvc_remote_evidence(
        cast(Mapping[str, Any], payload["dvc_remote_verification"]),
        locked_bundle,
        runtime=runtime,
        verify_current_remote_config=require_physical_artifacts,
    )
    locked_device = str(cast(Mapping[str, Any], payload["environment"])["device"])
    if device is not None and device != locked_device:
        raise DevelopmentRuntimePatchError(
            f"Requested device {device!r} differs from E0-DLP device {locked_device!r}"
        )
    if require_published:
        (
            _,
            execution_head,
            published_ref,
            published_head,
            remote_main_oid,
        ) = _require_patch_published(
            patch_lock_path, verify_remote=require_physical_artifacts
        )
        _validate_patch_publication_bundle(
            payload,
            execution_head=execution_head,
            published_head=published_head,
        )
        _require_ancestor(patch_head, execution_head)
        _require_ancestor(patch_head, published_head)
    else:
        execution_head = current_execution_head
        published_ref = None
        published_head = None
        remote_main_oid = None
    _require_ancestor(patch_head, execution_head)
    if execution_head != current_execution_head:
        raise DevelopmentRuntimePatchError("Execution HEAD changed during E0-DLP validation")
    _validate_effective_patch_records_at_execution(payload, execution_head)
    summary = _legacy_summary(
        base=base,
        relative_base_lock_path=_relative(base_lock_path),
        execution_head=execution_head,
        published_ref=published_ref,
        published_head=published_head,
        remote_main_oid=remote_main_oid,
        require_published=require_published,
        require_physical_artifacts=require_physical_artifacts,
    )
    return dict(payload), summary


def require_development_fit_authorized_with_patch(
    *,
    device: str | None = None,
    patch_lock_path: Path = DEFAULT_PATCH_LOCK_PATH,
    patch_lock_schema: Path = DEFAULT_PATCH_LOCK_SCHEMA,
) -> dict[str, Any]:
    """Fail closed unless published E0-DLP authorizes development fit only."""
    _, summary = load_and_validate_development_runtime_patch_lock(
        patch_lock_path,
        patch_lock_schema,
        device=device,
        require_published=True,
        require_physical_artifacts=True,
    )
    if summary.get("fit_authorized") is not True or summary.get(
        "development_fit_authorized"
    ) is not True:
        raise DevelopmentRuntimePatchError("E0-DLP did not authorize development fit")
    if (
        summary.get("evaluation_authorized") is not False
        or summary.get("e0_u_authorized") is not False
        or summary.get("future_outcomes_accessed") is not False
    ):
        raise DevelopmentRuntimePatchError("E0-DLP evaluation/outcome seals drifted")
    return summary


__all__ = [
    "BASE_COMPONENT_DRIFT_ALLOWLIST",
    "DEFAULT_PATCH_LOCK_PATH",
    "DEFAULT_PATCH_LOCK_SCHEMA",
    "DevelopmentRuntimePatchError",
    "LEGACY_SUMMARY_KEYS",
    "PATCH_FOCUSED_TEST_COMMAND",
    "PATCH_LOCK_VERSION",
    "adopted_seed_bundle_record",
    "build_development_runtime_patch_lock_payload",
    "collect_patch_prelock_state",
    "load_and_validate_development_runtime_patch_lock",
    "patch_dvc_remote_push_command",
    "require_adopted_seed_1729_consumer_context",
    "require_development_fit_authorized_with_patch",
    "validate_development_runtime_patch_lock_payload",
    "verify_patch_dvc_remote_by_idempotent_push",
]
