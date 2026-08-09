#!/usr/bin/env python
"""Prepare Git and DVC artifacts before a manual commit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import stat
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _ensure_project_root_importable() -> None:
    """Make absolute ``src.*`` imports work for the direct script entrypoint."""
    project_root = str(PROJECT_ROOT)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


_ensure_project_root_importable()


DEFAULT_DVC_MANIFEST = Path("configs/dvc_artifacts.yaml")
DEFAULT_CLOSURE_DVC_MANIFEST = Path(
    "configs/closure_v1/dvc_artifacts_post_lock.yaml"
)
DEFAULT_REPORT_DIR = Path("tmp")
DEFAULT_DVC_BIN = Path(".venv/bin/dvc")
DEFAULT_DVC_SITE_CACHE_DIR = Path(".dvc/tmp/site-cache")
HASH_CHUNK_SIZE = 16 * 1024 * 1024
DEFAULT_MAX_MANIFEST_HASH_BYTES = 512 * 1024 * 1024

# E0-MV/E0-MW/E0-MX is the sole exception to the normal immediate ``dvc add`` policy.  Its
# first one-shot model bundle must stay byte-exact and unregistered until all
# ten A0/A1 slots exist.  Keep this inventory local to the assistant so the
# exception cannot silently grow with a mutable experiment module.
DEFERRED_DVC_MODELS_TARGET = Path("models")
DEFERRED_DVC_MODELS_POINTER = Path("models.dvc")
DEFERRED_DVC_MODELS_POINTER_SHA256 = (
    "fcb93f78cc3e60c1c7f5bcc94a1765080358e0a5176880f1efa6245fa5365e5d"
)
DEFERRED_DVC_MODELS_DIRECTORY_MD5 = "fc60851634c1345cc5dc2c9169be9e1c"
DEFERRED_DVC_MODELS_DIRECTORY_SHA256 = (
    "f40b5ca2ddfff0e99f12db5ea9a6360ea6d62830856c4a0e09ef0c870d1b1eb1"
)
DEFERRED_DVC_MODELS_DIRECTORY_BYTES = 34_581
DEFERRED_DVC_MODELS_NFILES = 248
DEFERRED_DVC_MODELS_BYTES = 124_717_666
DEFERRED_DVC_MODELS_STATUS = {
    "models.dvc": [{"changed outs": {"models": "modified"}}]
}
DEFERRED_DVC_A0_FINAL_RECORDS = (
    (
        "model",
        "models/closure_v1/anfis_ablation/A0/seed_1729.pt",
        142_911,
        "1e5c2c21b9cb69a4dfa9139fcd6058e57afd4922a19bd1b3cd071a6608897fef",
    ),
    (
        "checkpoint",
        "models/closure_v1/anfis_ablation/A0/seed_1729.checkpoint.pt",
        142_911,
        "0991ff130f694b69ae30bd37416d3ba2d63f67874b3d895976efb9e28c6ce277",
    ),
    (
        "preprocessor",
        "reports/closure_v1/02_models/A0/seed_1729_preprocessor.json",
        2_472,
        "ebffd11d392c62e68e2afbd3ee05febfd05a7411fc83ca18563c7773a51faa62",
    ),
    (
        "training_curve",
        "reports/closure_v1/02_models/A0/seed_1729_training_curve.csv",
        2_588,
        "edfb193302b0fe21708e1ff1556dcdcdf817948a8bd35cef2f90b16be9cc0ec0",
    ),
    (
        "selection_predictions",
        "data/closure_v1/development/anfis_ablation/A0/seed_1729_selection_predictions.parquet",
        64_842,
        "6ca58207a32ba345fc4611c73a879e0546a608d7d076baf8f8da057373a3a4ae",
    ),
    (
        "selection_metrics",
        "reports/closure_v1/02_models/A0/seed_1729_selection_metrics.csv",
        914,
        "f6444a2047d2032334580f1322c4f61637a9028fd0aab27815a6c7386cf860eb",
    ),
    (
        "report",
        "reports/closure_v1/02_models/A0/seed_1729_report.md",
        320,
        "6e12b1d2fc0a1fce8baf7c1f81edbeb1bdd3d013d4365d606d21cc20399d123e",
    ),
    (
        "manifest",
        "reports/closure_v1/02_models/A0/seed_1729_manifest.json",
        11_231,
        "406bf44de3ecdc49ff3d5797cbca1ec0c11ebfbdc70ba262130b85a2e58e31e2",
    ),
)
DEFERRED_DVC_A0_LIGHT_EXCLUDE_PATTERNS = tuple(
    sorted(
        f"/{path}"
        for _, path, _, _ in DEFERRED_DVC_A0_FINAL_RECORDS
        if path.startswith("reports/")
    )
)
DEFERRED_DVC_A0_LIGHT_PUBLICATION_COMMIT = (
    "5b24549f2d4791f6500e661f9ee404c0dc7a0866"
)
DEFERRED_DVC_A0_LIGHT_PUBLICATION_PARENT = (
    "68107147c1a67c30ecfa64c862dd39531e574a9a"
)
DEFERRED_DVC_A0_LIGHT_GIT_OIDS = {
    "reports/closure_v1/02_models/A0/seed_1729_manifest.json": (
        "9d554bc0b560b2a4e817f2eb8d07ef48424dd51a"
    ),
    "reports/closure_v1/02_models/A0/seed_1729_preprocessor.json": (
        "b59088160da3c8d36efb984260f021959d52dddb"
    ),
    "reports/closure_v1/02_models/A0/seed_1729_report.md": (
        "740ef989b27bcbb44c22b81d4d90f9722d8f55b3"
    ),
    "reports/closure_v1/02_models/A0/seed_1729_selection_metrics.csv": (
        "90ee68a227fd02d5554b6a256f8bde6927ec36a6"
    ),
    "reports/closure_v1/02_models/A0/seed_1729_training_curve.csv": (
        "6b0a676116a34a41d36956696ba945c9632abecd"
    ),
}
DEFERRED_DVC_A0_PREDICTION_POINTER = Path(
    "data/closure_v1/development/anfis_ablation/A0/"
    "seed_1729_selection_predictions.parquet.dvc"
)
DEFERRED_DVC_A0_GUARD = Path(
    "tmp/closure_v1_anfis_ablation_training/A0_seed_1729.guard"
)
DEFERRED_DVC_H_MV_STAGED_SCOPE = {
    "configs/closure_v1/anfis_ablation_model_manifest_patch_lock.schema.json": "A",
    "docs/closure_v1/E0_M_ANFIS_ABLATION_MODEL_MANIFEST_PATCH_1.md": "A",
    "src/data/prepare_commit_artifacts.py": "M",
    "src/experiments/audit_closure_anfis_ablation_model_bundle.py": "M",
    "src/experiments/closure_anfis_ablation_model_manifest_patch.py": "A",
    "src/experiments/lock_closure_anfis_ablation_model_manifest_patch.py": "A",
    "src/experiments/train_closure_anfis_ablation.py": "M",
    "tests/test_audit_closure_anfis_ablation_model_bundle.py": "M",
    "tests/test_closure_anfis_ablation_model_manifest_patch.py": "A",
    "tests/test_train_closure_anfis_ablation.py": "M",
}
DEFERRED_DVC_P_MV_STAGED_SCOPE = {
    "reports/closure_v1/00_protocol/anfis_ablation_model_manifest_patch_lock.json": "A",
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_model_manifest_patch_lock_manifest.json"
    ): "A",
}
DEFERRED_DVC_H_MV_GIT_MODES = {
    path: ("100755" if path == "src/data/prepare_commit_artifacts.py" else "100644")
    for path in DEFERRED_DVC_H_MV_STAGED_SCOPE
}
DEFERRED_DVC_P_MV_GIT_MODES = {
    path: "100644" for path in DEFERRED_DVC_P_MV_STAGED_SCOPE
}
DEFERRED_DVC_H_MW_STAGED_SCOPE = {
    "configs/closure_v1/anfis_ablation_model_publication_patch_lock.schema.json": "A",
    "docs/closure_v1/E0_M_ANFIS_ABLATION_MODEL_PUBLICATION_PATCH_1.md": "A",
    "src/data/prepare_commit_artifacts.py": "M",
    "src/experiments/audit_closure_anfis_ablation_model_bundle.py": "M",
    "src/experiments/closure_anfis_ablation_model_publication_patch.py": "A",
    "src/experiments/lock_closure_anfis_ablation_model_publication_patch.py": "A",
    "src/experiments/train_closure_anfis_ablation.py": "M",
    "tests/test_audit_closure_anfis_ablation_model_bundle.py": "M",
    "tests/test_closure_anfis_ablation_model_publication_patch.py": "A",
    "tests/test_train_closure_anfis_ablation.py": "M",
}
DEFERRED_DVC_P_MW_STAGED_SCOPE = {
    "reports/closure_v1/00_protocol/anfis_ablation_model_publication_patch_lock.json": "A",
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_model_publication_patch_lock_manifest.json"
    ): "A",
}
DEFERRED_DVC_H_MW_GIT_MODES = {
    path: ("100755" if path == "src/data/prepare_commit_artifacts.py" else "100644")
    for path in DEFERRED_DVC_H_MW_STAGED_SCOPE
}
DEFERRED_DVC_P_MW_GIT_MODES = {
    path: "100644" for path in DEFERRED_DVC_P_MW_STAGED_SCOPE
}
DEFERRED_DVC_H_MX_STAGED_SCOPE = {
    "configs/closure_v1/anfis_ablation_model_publication_adoption_patch_lock.schema.json": "A",
    "docs/closure_v1/E0_M_ANFIS_ABLATION_MODEL_PUBLICATION_ADOPTION_PATCH_1.md": "A",
    "src/data/prepare_commit_artifacts.py": "M",
    "src/experiments/audit_closure_anfis_ablation_model_bundle.py": "M",
    "src/experiments/closure_anfis_ablation_model_publication_adoption_patch.py": "A",
    "src/experiments/lock_closure_anfis_ablation_model_publication_adoption_patch.py": "A",
    "src/experiments/train_closure_anfis_ablation.py": "M",
    "tests/test_audit_closure_anfis_ablation_model_bundle.py": "M",
    "tests/test_closure_anfis_ablation_model_publication_adoption_patch.py": "A",
    "tests/test_closure_anfis_ablation_model_publication_patch.py": "M",
    "tests/test_train_closure_anfis_ablation.py": "M",
}
DEFERRED_DVC_P_MX_STAGED_SCOPE = {
    "reports/closure_v1/00_protocol/anfis_ablation_model_publication_adoption_patch_lock.json": "A",
    (
        "reports/closure_v1/00_protocol/"
        "anfis_ablation_model_publication_adoption_patch_lock_manifest.json"
    ): "A",
}
DEFERRED_DVC_H_MX_GIT_MODES = {
    path: ("100755" if path == "src/data/prepare_commit_artifacts.py" else "100644")
    for path in DEFERRED_DVC_H_MX_STAGED_SCOPE
}
DEFERRED_DVC_P_MX_GIT_MODES = {
    path: "100644" for path in DEFERRED_DVC_P_MX_STAGED_SCOPE
}
DEFERRED_DVC_ACTIVE_STAGING_GATES = frozenset({"H-E0-MX", "P-E0-MX"})


def _deferred_dvc_staged_scopes() -> dict[str, Mapping[str, str]]:
    """Resolve current scope maps so tests and callers cannot observe stale aliases."""
    return {
        "H-E0-MV": DEFERRED_DVC_H_MV_STAGED_SCOPE,
        "P-E0-MV": DEFERRED_DVC_P_MV_STAGED_SCOPE,
        "H-E0-MW": DEFERRED_DVC_H_MW_STAGED_SCOPE,
        "P-E0-MW": DEFERRED_DVC_P_MW_STAGED_SCOPE,
        "H-E0-MX": DEFERRED_DVC_H_MX_STAGED_SCOPE,
        "P-E0-MX": DEFERRED_DVC_P_MX_STAGED_SCOPE,
    }


def _deferred_dvc_git_modes() -> dict[str, Mapping[str, str]]:
    return {
        "H-E0-MV": DEFERRED_DVC_H_MV_GIT_MODES,
        "P-E0-MV": DEFERRED_DVC_P_MV_GIT_MODES,
        "H-E0-MW": DEFERRED_DVC_H_MW_GIT_MODES,
        "P-E0-MW": DEFERRED_DVC_P_MW_GIT_MODES,
        "H-E0-MX": DEFERRED_DVC_H_MX_GIT_MODES,
        "P-E0-MX": DEFERRED_DVC_P_MX_GIT_MODES,
    }


def require_active_deferred_dvc_staging_gate(gate: str) -> str:
    """Reject historical deferred-DVC scopes at the only mutating boundary."""
    if type(gate) is str and gate in DEFERRED_DVC_ACTIVE_STAGING_GATES:
        return gate
    # Published MV/MW regression harnesses exercise the transaction with every
    # Git/DVC operation replaced inside a directory that is not a repository.
    # Preserve that read-only reconstruction without admitting MV/MW at a
    # real repository mutation boundary.
    if (
        type(gate) is str
        and gate in {"H-E0-MV", "P-E0-MV", "H-E0-MW", "P-E0-MW"}
        and not Path(".git").exists()
    ):
        return gate
    raise DeferredDvcTargetError(
        "Deferred models execution is closed to exact H-E0-MX/P-E0-MX scopes"
    )


HEAVY_PREFIXES = (
    "data/raw/",
    "data/interim/",
    "data/cache/",
    "data/panel/",
    "data/targets/",
    "data/splits/",
    "data/diagnostics/",
    "data/fuzzy/",
    "data/pipe_grud/",
    "data/closure_v1/",
    "models/",
    "checkpoints/",
    "outputs/",
    "artifacts/",
    "runs/",
    "mlruns/",
    "wandb/",
)
IGNORED_PREFIXES_TO_SKIP = (
    ".dvc/cache/",
    ".dvc/tmp/",
    ".pytest_cache/",
    ".venv/",
    "private/",
)
IGNORED_PATH_PARTS_TO_SKIP = {
    "__pycache__",
    ".ipynb_checkpoints",
}
REPORT_SMOKE_PARQUET_SUFFIXES = ("_smoke.parquet", "_stochastic_smoke.parquet")
REGENERABLE_IGNORED_PATHS = {
    "data/interim/observations/observations_summary.csv",
}
REPORT_ARTIFACT_SUFFIXES = {".csv", ".json", ".md", ".parquet", ".txt"}
CLOSURE_PROTOCOL_LOCK_PATH = Path("reports/closure_v1/00_protocol/protocol_lock.json")
CLOSURE_PROTOCOL_LOCK_VERSION = "closure_protocol_lock_v1"
CLOSURE_PROTOCOL_LOCK_SCRIPT = Path("src/experiments/lock_closure_protocol.py")
CLOSURE_DEVELOPMENT_RUNTIME_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/development_runtime_lock.json"
)
CLOSURE_DEVELOPMENT_RUNTIME_LOCK_SCHEMA = Path(
    "configs/closure_v1/development_runtime_lock.schema.json"
)
CLOSURE_DEVELOPMENT_RUNTIME_LOCK_VERSION = "closure_development_runtime_lock_v1"
CLOSURE_COMMON_ORIGIN_MANIFEST_PATH = Path(
    "reports/closure_v1/01_surface/common_origin_manifest.json"
)
CLOSURE_COMMON_ORIGIN_MANIFEST_VERSION = "closure_common_origin_manifest_v1"
CLOSURE_COMMON_ORIGIN_MANIFEST_SCRIPT = Path(
    "src/experiments/build_common_origin_manifest.py"
)
CLOSURE_COMMON_ORIGIN_OUTPUT_PATH = Path(
    "data/closure_v1/common_origin_manifest.parquet"
)
CLOSURE_EXPERT_STATE_MANIFEST_PATH = Path(
    "reports/closure_v1/01_surface/expert/expert_no_current_state_manifest.json"
)
CLOSURE_EXPERT_STATE_OUTPUT_PATH = Path(
    "data/closure_v1/development/expert/expert_no_current_state.parquet"
)
CLOSURE_MIFAL_DEVELOPMENT_MANIFEST_PATH = Path(
    "reports/closure_v1/02_models/M0/manifest.json"
)
CLOSURE_MIFAL_DEVELOPMENT_MANIFEST_SCHEMA_VERSION = (
    "closure_mifal_development_manifest_v1"
)
CLOSURE_MIFAL_DEVELOPMENT_MANIFEST_STATUS = (
    "mifal_development_bundle_written_unpublished"
)
CLOSURE_MIFAL_DEVELOPMENT_SCRIPT = Path(
    "src/experiments/run_closure_mifal.py"
)
CLOSURE_MIFAL_DEVELOPMENT_OUTPUT_PATHS = (
    Path("data/closure_v1/development/mifal/M0/raw_scores.parquet"),
    Path("reports/closure_v1/02_models/M0/model_spec.json"),
    Path("reports/closure_v1/02_models/M0/lineage_audit.json"),
    Path("reports/closure_v1/02_models/M0/availability.csv"),
    Path("reports/closure_v1/02_models/M0/report.md"),
)
CLOSURE_MIFAL_DEVELOPMENT_SOURCE_PATHS = (
    Path("src/mifal/ed_t2.py"),
    CLOSURE_MIFAL_DEVELOPMENT_SCRIPT,
    Path("src/mifal/closure_panel_adapter.py"),
)
CLOSURE_MIFAL_DEVELOPMENT_INPUT_PATHS_AND_ROLES = (
    (Path("reports/closure_v1/00_protocol/protocol_lock.json"), "protocol_lock"),
    (
        Path("reports/closure_v1/00_protocol/development_runtime_lock.json"),
        "development_runtime_lock",
    ),
    (
        Path(
            "reports/closure_v1/00_protocol/"
            "development_runtime_temporal_validation_dialect_patch_lock.json"
        ),
        "effective_development_runtime_lock",
    ),
    (
        Path(
            "reports/closure_v1/00_protocol/"
            "development_runtime_temporal_validation_dialect_patch_lock_manifest.json"
        ),
        "effective_development_runtime_lock_manifest",
    ),
    (Path("src/experiments/closure_development_guard.py"), "development_guard"),
    (
        Path("data/closure_v1/closure_holdout_assignment.csv"),
        "holdout_assignment",
    ),
    (
        Path("reports/closure_v1/00_protocol/holdout_manifest.json"),
        "holdout_manifest",
    ),
    (
        Path("data/closure_v1/common_origin_manifest.parquet"),
        "common_origin",
    ),
    (
        Path("data/closure_v1/common_origin_manifest.parquet.dvc"),
        "common_origin_pointer",
    ),
    (
        Path("reports/closure_v1/01_surface/common_origin_manifest.json"),
        "common_origin_manifest",
    ),
    (Path("data/panel/panel_monthly_v0.parquet"), "panel"),
    (Path("data/panel/panel_monthly_v0.parquet.dvc"), "panel_pointer"),
    (Path("configs/closure_v1/model_benchmark.yaml"), "model_benchmark"),
    (Path("configs/closure_v1/surface_primary.yaml"), "primary_surface"),
    (Path("configs/closure_v1/analysis_plan.yaml"), "analysis_plan"),
    (
        Path("configs/closure_v1/experimental_matrix.yaml"),
        "experimental_matrix",
    ),
    (Path("src/mifal/ed_t2.py"), "mifal_core"),
    (Path("pyproject.toml"), "pyproject"),
    (Path("poetry.lock"), "poetry_lock"),
    (
        Path("reports/closure_v1/02_models/baselines/manifest.json"),
        "upstream_baseline_manifest",
    ),
    (
        Path(
            "reports/closure_v1/00_protocol/"
            "baseline_development_publication_guard_patch_lock.json"
        ),
        "upstream_baseline_patch_lock",
    ),
    (
        Path(
            "reports/closure_v1/00_protocol/"
            "baseline_development_publication_guard_patch_lock_manifest.json"
        ),
        "upstream_baseline_patch_lock_manifest",
    ),
    (Path("models.dvc"), "models_dvc_observer"),
    (
        Path("configs/closure_v1/mifal_development_runtime.yaml"),
        "mifal_runtime",
    ),
    (
        Path("reports/closure_v1/00_protocol/mifal_development_patch_lock.json"),
        "effective_patch_lock",
    ),
    (
        Path(
            "reports/closure_v1/00_protocol/"
            "mifal_development_patch_lock_manifest.json"
        ),
        "effective_patch_lock_manifest",
    ),
    (CLOSURE_MIFAL_DEVELOPMENT_SCRIPT, "mifal_development_runner"),
    (Path("src/mifal/closure_panel_adapter.py"), "strict_panel_adapter"),
)
CLOSURE_MIFAL_RAW_PREDICTION_CONTRACT_SHA256 = (
    "e6e50951d083e0109f9a7395ab711edc318d8c80b0c11b7e5d7de8f086eaf2e1"
)
CLOSURE_MIFAL_EXPECTED_AUTHORITY = {
    "gate": "E0-MR",
    "status": "effective_preflight_passed",
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
    "h_patch_head": "4dab0a286f4df31c95251fde7f9e36ee7d09e968",
    "p_patch_head": "9106ff042ecea135d3652e8dedac4d78a2360b3e",
    "lock_sha256": "59eb0674ae4502bcbae16b9ad0f4c653429771e3c9ec89b1ef1f31e3dbb08125",
    "companion_sha256": "3628973b4eda30b14787f57554bef8b13d8c9580d1b3c3f2c4134acb7c3130f9",
    "runtime_sha256": "26a1e2fa6f7d630cbe770dd282f8d86b21a152f4733874ecc6b19de53b5e7d84",
    "h_components_sha256": "8bfad66fb5e2c2072e815966b85bff207f501ddf7cdc680fbadcefe8f44b8955",
    "physical_inputs_sha256": "49ffcc28dec8ea2306d46b2f5b274a318ec7d8d2c94a36ea5fa970fa059b16d3",
    "runner_sha256": "a4afeeeb475d0cc4d9532ed92e5a05d1b37ca73e2b9bf8755d224f7b1fc3d6f4",
    "adapter_sha256": "d9438eacd4dfdd1127a2cf22398de420802c8044948b548dccd23d28fbde4773",
    "mifal_core_sha256": "46490b08e6efd2725c14ba4cd07eede2b06b191179d25d1ffecf189efec1ca53",
    "exact_raw_prediction_rows": 29196,
    "minimum_observed_evidence_groups": 2,
}
CLOSURE_MIFAL_EXPECTED_COUNTS = {
    "raw_rows": 29196,
    "intent_origins": 9732,
    "eligible_origins": 9732,
    "input_ineligible_origins": 0,
    "development_locations": 353,
    "final_paths": 6,
}
CLOSURE_MIFAL_MANIFEST_FALSE_FLAGS = (
    "tuning_performed",
    "targets_opened",
    "calibration_performed",
    "metrics_computed",
    "e0_m_authorized",
    "evaluation_authorized",
    "e0_u_authorized",
    "dvc_commands_run",
    "network_calls_made",
    "future_outcomes_accessed",
)
CLOSURE_COMMON_ORIGIN_CODE_PATHS = (
    CLOSURE_COMMON_ORIGIN_MANIFEST_SCRIPT,
    Path("src/experiments/build_closure_holdout.py"),
    Path("src/experiments/closure_contract.py"),
    Path("src/experiments/closure_development_guard.py"),
    Path("src/pandas_utils.py"),
)
CLOSURE_COMMON_ORIGIN_CONFIG_PATHS = (
    Path("configs/closure_v1/analysis_plan.yaml"),
    Path("configs/closure_v1/analysis_plan.schema.json"),
    Path("configs/closure_v1/surface_primary.yaml"),
    Path("configs/closure_v1/surface_secondary.yaml"),
    Path("configs/closure_v1/location_holdout.yaml"),
    Path("configs/closure_v1/model_benchmark.yaml"),
    Path("configs/closure_v1/experimental_matrix.yaml"),
    Path("configs/counterfactual_planning_v1.yaml"),
)
CLOSURE_COMMON_ORIGIN_SOURCE_PATHS = (
    Path("data/panel/panel_monthly_v0.parquet"),
    Path("data/splits/monthly_model_splits_v0.parquet"),
    Path("data/targets/monthly_targets_model_v0.parquet"),
    Path("data/targets/target_manifest_v0.json"),
    Path("data/splits/split_manifest.json"),
)
CLOSURE_COMMON_ORIGIN_SOURCE_ROLES = (
    "cutoff_safe_input_history_source",
    "canonical_leakage_safe_temporal_rows",
    "historical_stratification_and_later_evaluation_targets",
    "canonical_target_provenance_and_threshold_manifest",
    "temporal_split_provenance",
)
CLOSURE_COMMON_ORIGIN_PARENT_PATHS_AND_ROLES = (
    (Path("reports/closure_v1/00_protocol/protocol_lock.json"), "protocol_lock"),
    (Path("reports/closure_v1/00_protocol/holdout_manifest.json"), "holdout_manifest"),
    (Path("data/closure_v1/closure_holdout_assignment.csv"), "holdout_assignment"),
)
CLOSURE_COMMON_ORIGIN_REPRODUCTION_COMMAND = [
    "poetry",
    "run",
    "python",
    CLOSURE_COMMON_ORIGIN_MANIFEST_SCRIPT.as_posix(),
    "--panel",
    CLOSURE_COMMON_ORIGIN_SOURCE_PATHS[0].as_posix(),
    "--splits",
    CLOSURE_COMMON_ORIGIN_SOURCE_PATHS[1].as_posix(),
    "--output",
    CLOSURE_COMMON_ORIGIN_OUTPUT_PATH.as_posix(),
    "--manifest",
    CLOSURE_COMMON_ORIGIN_MANIFEST_PATH.as_posix(),
]
FREEZE_ARTIFACT_PATHS = {
    Path("data/freeze/derived_file_manifest_v0.csv"),
    Path("data/freeze/data_freeze_manifest_v0.json"),
    Path("data/freeze/DATA_FREEZE.md"),
}
FREEZE_REQUIRED_OUTPUTS = {
    Path("data/freeze/derived_file_manifest_v0.csv"),
    Path("data/freeze/data_freeze_manifest_v0.json"),
    Path("data/freeze/DATA_FREEZE.md"),
}
FREEZE_DOCUMENTATION_OUTPUTS = {
    Path("data/freeze/data_freeze_manifest_v0.json"),
    Path("data/freeze/DATA_FREEZE.md"),
}
FREEZE_SENSITIVE_EXACT_PATHS = {
    "configs/sources.yaml",
    "configs/site_resolution.yaml",
    "src/data/build_observations.py",
    "src/data/build_waterbody_crosswalk.py",
    "src/data/build_panel.py",
    "src/data/build_targets.py",
    "src/data/diagnose_panel_targets.py",
    "src/data/freeze.py",
    "src/data/raw_manifest.py",
    "src/data/report_observations.py",
    "src/data/site_registry.py",
    "src/data/validate_sources.py",
}
FREEZE_SENSITIVE_PREFIXES = (
    "data/catalog/",
    "data/interim/",
    "data/panel/",
    "data/targets/",
    "data/diagnostics/",
    "data/scripts/",
)
DEFAULT_DVC_ARTIFACT_INVENTORY = Path("configs/dvc_artifacts.yaml")


@dataclass(frozen=True)
class DvcArtifact:
    artifact_id: str
    path: Path
    artifact_type: str
    source_id: str
    dvc: bool


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class ReproducibilityFinding:
    level: str
    check: str
    path: str
    message: str


@dataclass(frozen=True)
class DeferredDvcFinalSnapshot:
    path: str
    device: int
    inode: int
    mtime_ns: int
    size: int
    sha256: str
    mode: int
    nlink: int = 1
    ctime_ns: int = 0


class DeferredDvcTargetError(RuntimeError):
    """Raised when the closed model-bundle DVC-deferral exception drifts."""


def command_text(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def sha256_file(path: Path, chunk_size: int = HASH_CHUNK_SIZE) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _md5_file(path: Path, chunk_size: int = HASH_CHUNK_SIZE) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_regular_file(path: Path, *, mode: int | None = None) -> os.stat_result:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise DeferredDvcTargetError(f"Required deferred-DVC file is absent: {path}") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise DeferredDvcTargetError(f"Deferred-DVC path is not a regular file: {path}")
    if mode is not None and stat.S_IMODE(metadata.st_mode) != mode:
        raise DeferredDvcTargetError(
            f"Deferred-DVC file mode drifted: {path} "
            f"({stat.S_IMODE(metadata.st_mode):04o} != {mode:04o})"
        )
    return metadata


def _require_no_symlink_ancestors(path: Path, *, anchor: Path) -> None:
    try:
        relative = path.relative_to(anchor)
    except ValueError as exc:
        raise DeferredDvcTargetError(
            f"Deferred-DVC path escapes its lexical anchor: {path}"
        ) from exc
    current = anchor
    if not stat.S_ISDIR(current.lstat().st_mode):
        raise DeferredDvcTargetError(
            f"Deferred-DVC lexical anchor is not a directory: {anchor}"
        )
    for part in relative.parts[:-1]:
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError as exc:
            raise DeferredDvcTargetError(
                f"Deferred-DVC lexical ancestor is absent: {current}"
            ) from exc
        if not stat.S_ISDIR(metadata.st_mode):
            raise DeferredDvcTargetError(
                f"Deferred-DVC lexical ancestor is not a directory: {current}"
            )


def validate_deferred_dvc_git_exclude_environment(
    *, env: Mapping[str, str] | None = None
) -> tuple[int, int, int, str]:
    """Validate the exact command-scoped Git exclusion used through E0-MX.

    E0-MX retains the five-path file to neutralize ambient global excludes and
    preserve the inherited command shape.  The five reports are now tracked,
    so their HEAD/index/worktree bindings are validated independently.
    """
    source = os.environ if env is None else env
    expected_names = {"GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0"}
    observed_names = {
        name
        for name in source
        if name.startswith("GIT_CONFIG")
    }
    if observed_names != expected_names:
        raise DeferredDvcTargetError(
            "Deferred models DVC target requires exactly one command-scoped Git config entry"
        )
    if source.get("GIT_CONFIG_COUNT") != "1" or source.get("GIT_CONFIG_KEY_0") != "core.excludesFile":
        raise DeferredDvcTargetError(
            "Deferred models DVC target requires GIT_CONFIG_COUNT=1 and core.excludesFile"
        )
    raw_path = source.get("GIT_CONFIG_VALUE_0")
    if not isinstance(raw_path, str) or not raw_path:
        raise DeferredDvcTargetError("Deferred models DVC exclude-file path is absent")
    exclude_path = Path(raw_path)
    if not exclude_path.is_absolute():
        raise DeferredDvcTargetError("Deferred models DVC exclude-file path must be absolute")
    redirected_git_environment = {
        "GIT_INDEX_FILE",
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_COMMON_DIR",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_NAMESPACE",
    }
    present_redirects = sorted(redirected_git_environment.intersection(source))
    if present_redirects:
        raise DeferredDvcTargetError(
            "Deferred models DVC mode forbids redirected Git state: "
            + ", ".join(present_redirects)
        )
    metadata = _require_regular_file(exclude_path, mode=0o600)
    _require_no_symlink_ancestors(exclude_path, anchor=Path(exclude_path.anchor))
    if metadata.st_nlink != 1:
        raise DeferredDvcTargetError(
            "Deferred models DVC exclude file must have exactly one hard link"
        )
    expected = "".join(f"{pattern}\n" for pattern in DEFERRED_DVC_A0_LIGHT_EXCLUDE_PATTERNS)
    try:
        payload = exclude_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise DeferredDvcTargetError("Deferred models DVC exclude file is not UTF-8") from exc
    if payload != expected:
        raise DeferredDvcTargetError(
            "Deferred models DVC exclude file must contain the exact five rooted A0 paths"
        )
    return (metadata.st_dev, metadata.st_ino, metadata.st_mtime_ns, sha256_file(exclude_path))


def normalize_deferred_dvc_targets(
    raw_targets: list[str], *, no_push: bool
) -> list[Path]:
    if not raw_targets:
        return []
    if raw_targets != [DEFERRED_DVC_MODELS_TARGET.as_posix()]:
        raise DeferredDvcTargetError(
            "The only supported deferred DVC target is the single exact path: models"
        )
    if not no_push:
        raise DeferredDvcTargetError("Deferred DVC targets require --no-push")
    return [DEFERRED_DVC_MODELS_TARGET]


def validate_deferred_dvc_invocation(
    args: Any,
    deferred_paths: list[Path],
    *,
    env: Mapping[str, str] | None = None,
) -> None:
    if not deferred_paths:
        return
    source = os.environ if env is None else env
    dvc_site_cache = source.get("DVC_SITE_CACHE_DIR")
    if (
        args.yes
        or args.dry_run
        or args.skip_publication_check
        or args.jobs is not None
        or not args.allow_unmanaged
        or args.dvc_bin is not None
        or args.manifest != DEFAULT_DVC_MANIFEST
        or args.report is not None
        or "DVC_BIN" in source
        or source.get("DVC_NO_ANALYTICS") != "1"
        or (
            dvc_site_cache is not None
            and dvc_site_cache != DEFAULT_DVC_SITE_CACHE_DIR.as_posix()
        )
    ):
        raise DeferredDvcTargetError(
            "Deferred models mode requires --allow-unmanaged --no-push and forbids "
            "--yes, --dry-run, --jobs, --skip-publication-check, custom DVC binaries, "
            "custom DVC manifests, custom report paths, analytics-enabled DVC, and "
            "custom DVC site-cache paths"
        )


def validate_deferred_dvc_target_selection(
    deferred_paths: list[Path],
    *,
    artifacts: list[DvcArtifact],
    changed_artifacts: list[DvcArtifact],
    missing_pointer_artifacts: list[DvcArtifact],
    manual_targets: list[Path],
) -> None:
    if not deferred_paths:
        return
    configured = [
        artifact
        for artifact in artifacts
        if artifact.dvc and artifact.path == DEFERRED_DVC_MODELS_TARGET
    ]
    if len(configured) != 1 or not DEFERRED_DVC_MODELS_TARGET.exists():
        raise DeferredDvcTargetError(
            "Deferred models target must be one present configured DVC artifact"
        )
    if [artifact.path for artifact in changed_artifacts] != [DEFERRED_DVC_MODELS_TARGET]:
        raise DeferredDvcTargetError(
            "Deferred mode requires models to be the only changed DVC artifact"
        )
    if missing_pointer_artifacts:
        raise DeferredDvcTargetError("Deferred mode forbids missing DVC pointers")
    if manual_targets:
        raise DeferredDvcTargetError("Deferred mode forbids additional manual DVC targets")


def _git_output(repo_root: Path, *args: str) -> str:
    return run_command(["git", "-C", repo_root.as_posix(), *args]).stdout


def _validate_deferred_a0_git_tracking(repo_root: Path) -> None:
    """Bind the adopted lightweight A0 files to their exact publication commit."""
    light_paths = set(DEFERRED_DVC_A0_LIGHT_GIT_OIDS)
    expected_light_paths = {
        path
        for _, path, _, _ in DEFERRED_DVC_A0_FINAL_RECORDS
        if path.startswith("reports/")
    }
    if light_paths != expected_light_paths or len(light_paths) != 5:
        raise DeferredDvcTargetError(
            "Deferred A0 tracked-light inventory drifted from the exact five reports"
        )

    ancestry = _git_output(
        repo_root,
        "rev-list",
        "--parents",
        "-n",
        "1",
        DEFERRED_DVC_A0_LIGHT_PUBLICATION_COMMIT,
    ).strip()
    if ancestry != (
        f"{DEFERRED_DVC_A0_LIGHT_PUBLICATION_COMMIT} "
        f"{DEFERRED_DVC_A0_LIGHT_PUBLICATION_PARENT}"
    ):
        raise DeferredDvcTargetError(
            "Deferred A0 lightweight publication commit topology drifted"
        )
    merge_base = _git_output(
        repo_root,
        "merge-base",
        "HEAD",
        DEFERRED_DVC_A0_LIGHT_PUBLICATION_COMMIT,
    ).strip()
    if merge_base != DEFERRED_DVC_A0_LIGHT_PUBLICATION_COMMIT:
        raise DeferredDvcTargetError(
            "Deferred A0 lightweight publication commit is not a HEAD ancestor"
        )

    publication_scope: dict[str, str] = {}
    for line in _git_output(
        repo_root,
        "diff-tree",
        "--no-commit-id",
        "--name-status",
        "-r",
        DEFERRED_DVC_A0_LIGHT_PUBLICATION_COMMIT,
    ).splitlines():
        fields = line.split("\t")
        if len(fields) != 2 or fields[1] in publication_scope:
            raise DeferredDvcTargetError(
                "Deferred A0 lightweight publication commit scope is malformed"
            )
        publication_scope[fields[1]] = fields[0]
    if publication_scope != {path: "A" for path in light_paths}:
        raise DeferredDvcTargetError(
            "Deferred A0 lightweight publication commit is not the exact five additions"
        )

    for raw_path, expected_oid in sorted(DEFERRED_DVC_A0_LIGHT_GIT_OIDS.items()):
        publication_line = _git_output(
            repo_root,
            "ls-tree",
            DEFERRED_DVC_A0_LIGHT_PUBLICATION_COMMIT,
            "--",
            raw_path,
        ).strip()
        expected_line = f"100644 blob {expected_oid}\t{raw_path}"
        head_oid = _git_output(repo_root, "rev-parse", f"HEAD:{raw_path}").strip()
        index_line = _git_output(
            repo_root, "ls-files", "-s", "--", raw_path
        ).strip()
        worktree_oid = _git_output(
            repo_root, "hash-object", "--no-filters", "--", raw_path
        ).strip()
        if (
            publication_line != expected_line
            or head_oid != expected_oid
            or index_line != f"100644 {expected_oid} 0\t{raw_path}"
            or worktree_oid != expected_oid
        ):
            raise DeferredDvcTargetError(
                f"Deferred A0 lightweight Git binding drifted: {raw_path}"
            )

    ordered_light_paths = sorted(light_paths)
    if _git_output(
        repo_root, "diff", "--name-only", "--", *ordered_light_paths
    ).strip() or _git_output(
        repo_root, "diff", "--cached", "--name-only", "--", *ordered_light_paths
    ).strip():
        raise DeferredDvcTargetError(
            "Deferred A0 lightweight reports must be clean in index and worktree"
        )

    heavy_paths = sorted(
        path
        for _, path, _, _ in DEFERRED_DVC_A0_FINAL_RECORDS
        if path not in light_paths
    )
    if _git_output(
        repo_root, "ls-files", "--stage", "--", *heavy_paths
    ).strip():
        raise DeferredDvcTargetError(
            "Deferred A0 heavyweight finals must remain outside Git"
        )


def _validate_deferred_models_pointer(repo_root: Path) -> None:
    pointer = repo_root / DEFERRED_DVC_MODELS_POINTER
    _require_no_symlink_ancestors(pointer, anchor=repo_root)
    metadata = _require_regular_file(pointer, mode=0o644)
    if metadata.st_size != 109 or sha256_file(pointer) != DEFERRED_DVC_MODELS_POINTER_SHA256:
        raise DeferredDvcTargetError("models.dvc bytes drifted from the deferred-DVC baseline")
    try:
        payload = yaml.safe_load(pointer.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise DeferredDvcTargetError("models.dvc is not strict readable YAML") from exc
    expected = {
        "outs": [
            {
                "md5": f"{DEFERRED_DVC_MODELS_DIRECTORY_MD5}.dir",
                "size": DEFERRED_DVC_MODELS_BYTES,
                "nfiles": DEFERRED_DVC_MODELS_NFILES,
                "hash": "md5",
                "path": "models",
            }
        ]
    }
    if payload != expected:
        raise DeferredDvcTargetError("models.dvc descriptor dialect drifted")

    head_oid = _git_output(repo_root, "rev-parse", "HEAD:models.dvc").strip()
    worktree_oid = _git_output(repo_root, "hash-object", "models.dvc").strip()
    index_line = _git_output(repo_root, "ls-files", "-s", "--", "models.dvc").strip()
    if index_line != f"100644 {head_oid} 0\tmodels.dvc" or worktree_oid != head_oid:
        raise DeferredDvcTargetError("models.dvc HEAD/index/worktree binding drifted")
    if _git_output(repo_root, "diff", "--name-only", "--", "models.dvc").strip():
        raise DeferredDvcTargetError("models.dvc has an unstaged change")
    if _git_output(repo_root, "diff", "--cached", "--name-only", "--", "models.dvc").strip():
        raise DeferredDvcTargetError("models.dvc must not be staged by deferred mode")


def _walk_regular_tree(root: Path) -> dict[str, Path]:
    try:
        root_metadata = root.lstat()
    except FileNotFoundError as exc:
        raise DeferredDvcTargetError(f"Deferred-DVC tree is absent: {root}") from exc
    if not stat.S_ISDIR(root_metadata.st_mode):
        raise DeferredDvcTargetError(f"Deferred-DVC tree root is not a directory: {root}")
    result: dict[str, Path] = {}
    for current, directory_names, file_names in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in directory_names:
            candidate = current_path / name
            if not stat.S_ISDIR(candidate.lstat().st_mode):
                raise DeferredDvcTargetError(
                    f"Deferred-DVC tree contains a non-directory ancestor: {candidate}"
                )
        for name in file_names:
            candidate = current_path / name
            if not stat.S_ISREG(candidate.lstat().st_mode):
                raise DeferredDvcTargetError(
                    f"Deferred-DVC tree contains a non-regular file: {candidate}"
                )
            relative = candidate.relative_to(root).as_posix()
            if relative in result:
                raise DeferredDvcTargetError(f"Deferred-DVC tree path is duplicated: {relative}")
            result[relative] = candidate
    return result


def _validate_deferred_models_tree(repo_root: Path) -> None:
    descriptor_path = (
        repo_root
        / ".dvc/cache/files/md5"
        / DEFERRED_DVC_MODELS_DIRECTORY_MD5[:2]
        / f"{DEFERRED_DVC_MODELS_DIRECTORY_MD5[2:]}.dir"
    )
    _require_no_symlink_ancestors(descriptor_path, anchor=repo_root)
    descriptor_metadata = _require_regular_file(descriptor_path, mode=0o444)
    if (
        descriptor_metadata.st_size != DEFERRED_DVC_MODELS_DIRECTORY_BYTES
        or sha256_file(descriptor_path) != DEFERRED_DVC_MODELS_DIRECTORY_SHA256
        or _md5_file(descriptor_path) != DEFERRED_DVC_MODELS_DIRECTORY_MD5
    ):
        raise DeferredDvcTargetError("Deferred models DVC .dir descriptor drifted")
    try:
        records = json.loads(descriptor_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeferredDvcTargetError("Deferred models DVC .dir descriptor is invalid JSON") from exc
    if not isinstance(records, list) or len(records) != DEFERRED_DVC_MODELS_NFILES:
        raise DeferredDvcTargetError("Deferred models DVC .dir record count drifted")

    baseline: dict[str, str] = {}
    for record in records:
        if not isinstance(record, dict) or set(record) != {"md5", "relpath"}:
            raise DeferredDvcTargetError("Deferred models DVC .dir record dialect drifted")
        digest = record.get("md5")
        relative = record.get("relpath")
        if (
            not isinstance(digest, str)
            or len(digest) != 32
            or any(character not in "0123456789abcdef" for character in digest)
            or not isinstance(relative, str)
            or not relative
        ):
            raise DeferredDvcTargetError("Deferred models DVC .dir record is malformed")
        relative_path = Path(relative)
        if relative_path.is_absolute() or "." in relative_path.parts or ".." in relative_path.parts:
            raise DeferredDvcTargetError("Deferred models DVC .dir relpath is unsafe")
        if relative in baseline:
            raise DeferredDvcTargetError("Deferred models DVC .dir relpath is duplicated")
        baseline[relative] = digest
    if list(baseline) != sorted(baseline):
        raise DeferredDvcTargetError("Deferred models DVC .dir records are not canonically sorted")

    model_files = _walk_regular_tree(repo_root / DEFERRED_DVC_MODELS_TARGET)
    exact_extras = {
        Path(path).relative_to(DEFERRED_DVC_MODELS_TARGET).as_posix()
        for _, path, _, _ in DEFERRED_DVC_A0_FINAL_RECORDS
        if path.startswith("models/")
    }
    if set(model_files) != set(baseline) | exact_extras:
        raise DeferredDvcTargetError(
            "Deferred models DVC tree differs from 248 baseline files plus two exact A0 files"
        )
    total_bytes = 0
    for relative, digest in baseline.items():
        workspace_path = model_files[relative]
        cache_path = repo_root / ".dvc/cache/files/md5" / digest[:2] / digest[2:]
        _require_no_symlink_ancestors(cache_path, anchor=repo_root)
        cache_metadata = _require_regular_file(cache_path, mode=0o444)
        workspace_metadata = _require_regular_file(workspace_path)
        if _md5_file(cache_path) != digest or _md5_file(workspace_path) != digest:
            raise DeferredDvcTargetError(f"Deferred models DVC baseline object drifted: {relative}")
        if cache_metadata.st_size != workspace_metadata.st_size:
            raise DeferredDvcTargetError(f"Deferred models DVC baseline size drifted: {relative}")
        total_bytes += workspace_metadata.st_size
    if total_bytes != DEFERRED_DVC_MODELS_BYTES:
        raise DeferredDvcTargetError("Deferred models DVC baseline byte count drifted")


def snapshot_deferred_dvc_models_bundle(
    *, repo_root: Path = Path(".")
) -> tuple[DeferredDvcFinalSnapshot, ...]:
    snapshots: list[DeferredDvcFinalSnapshot] = []
    for _, raw_path, expected_bytes, expected_sha256 in DEFERRED_DVC_A0_FINAL_RECORDS:
        path = repo_root / raw_path
        _require_no_symlink_ancestors(path, anchor=repo_root)
        metadata = _require_regular_file(path, mode=0o644)
        if metadata.st_nlink != 1:
            raise DeferredDvcTargetError(
                f"Deferred A0 final must have one hard link: {raw_path}"
            )
        digest = sha256_file(path)
        if metadata.st_size != expected_bytes or digest != expected_sha256:
            raise DeferredDvcTargetError(f"Deferred A0 final bytes drifted: {raw_path}")
        snapshots.append(
            DeferredDvcFinalSnapshot(
                path=raw_path,
                device=metadata.st_dev,
                inode=metadata.st_ino,
                mtime_ns=metadata.st_mtime_ns,
                size=metadata.st_size,
                sha256=digest,
                mode=stat.S_IMODE(metadata.st_mode),
                nlink=metadata.st_nlink,
                ctime_ns=metadata.st_ctime_ns,
            )
        )
        temporary = Path(f"{path}.tmp")
        if os.path.lexists(temporary):
            raise DeferredDvcTargetError(f"Deferred A0 temporary is present: {temporary}")
    if snapshots[-1].mtime_ns <= max(record.mtime_ns for record in snapshots[:-1]):
        raise DeferredDvcTargetError("Deferred A0 manifest is not physically last")
    for prohibited in (
        repo_root / DEFERRED_DVC_A0_PREDICTION_POINTER,
        repo_root / Path(f"{DEFERRED_DVC_A0_PREDICTION_POINTER}.tmp"),
        repo_root / DEFERRED_DVC_A0_GUARD,
    ):
        if os.path.lexists(prohibited):
            raise DeferredDvcTargetError(f"Deferred A0 prohibited path is present: {prohibited}")
    report_root = repo_root / "reports/closure_v1/02_models/A0"
    expected_reports = {
        Path(record.path).name
        for record in snapshots
        if record.path.startswith("reports/")
    }
    if set(_walk_regular_tree(report_root)) != expected_reports:
        raise DeferredDvcTargetError(
            "Deferred A0 report namespace is not the exact five-file prefix"
        )
    prediction_root = repo_root / "data/closure_v1/development/anfis_ablation"
    expected_prediction = {
        Path(DEFERRED_DVC_A0_FINAL_RECORDS[4][1])
        .relative_to("data/closure_v1/development/anfis_ablation")
        .as_posix()
    }
    if set(_walk_regular_tree(prediction_root)) != expected_prediction:
        raise DeferredDvcTargetError(
            "Deferred A0 prediction namespace is not the exact one-file prefix"
        )
    if os.path.lexists(repo_root / "reports/closure_v1/02_models/A1"):
        raise DeferredDvcTargetError("Deferred A1 report namespace must remain absent")
    return tuple(snapshots)


def validate_deferred_dvc_models_state(
    dvc_status: Mapping[str, Any],
    *,
    repo_root: Path = Path("."),
    expected_final_snapshot: tuple[DeferredDvcFinalSnapshot, ...] | None = None,
) -> tuple[DeferredDvcFinalSnapshot, ...]:
    if dict(dvc_status) != DEFERRED_DVC_MODELS_STATUS:
        raise DeferredDvcTargetError(
            "Deferred models DVC status must be the exact single modified models output"
        )
    _validate_deferred_models_pointer(repo_root)
    _validate_deferred_models_tree(repo_root)
    snapshot = snapshot_deferred_dvc_models_bundle(repo_root=repo_root)
    if expected_final_snapshot is not None and snapshot != expected_final_snapshot:
        raise DeferredDvcTargetError("Deferred A0 inode/mtime/hash snapshot drifted")
    _validate_deferred_a0_git_tracking(repo_root)
    staged = _git_output(
        repo_root,
        "diff",
        "--cached",
        "--name-only",
        "--",
        *(record.path for record in snapshot),
    ).strip()
    if staged:
        raise DeferredDvcTargetError("Deferred A0 finals must not be staged")
    return snapshot


def sha256_directory(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    total_bytes = 0
    for file_path in sorted(item for item in path.rglob("*") if item.is_file() and not item.name.endswith(".tmp")):
        relative_path = file_path.relative_to(path).as_posix()
        file_hash = sha256_file(file_path)
        file_bytes = file_path.stat().st_size
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\0")
        total_bytes += file_bytes
    return total_bytes, digest.hexdigest()


def run_command(command: list[str], *, check: bool = True, env: dict[str, str] | None = None) -> CommandResult:
    process = subprocess.run(command, check=False, text=True, capture_output=True, env=env)
    result = CommandResult(
        command=command,
        returncode=process.returncode,
        stdout=process.stdout,
        stderr=process.stderr,
    )
    if check and result.returncode != 0:
        print(f"Command failed: {command_text(command)}", file=sys.stderr)
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)
    return result


def dvc_environment() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("DVC_SITE_CACHE_DIR", DEFAULT_DVC_SITE_CACHE_DIR.as_posix())
    return env


def resolve_dvc_bin(explicit_path: str | None) -> str:
    candidates = [
        explicit_path,
        os.environ.get("DVC_BIN"),
        DEFAULT_DVC_BIN.as_posix(),
        "dvc",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists() and os.access(path, os.X_OK):
            return path.as_posix()
        resolved = run_command(["bash", "-lc", f"command -v {shlex.quote(candidate)}"], check=False)
        if resolved.returncode == 0 and resolved.stdout.strip():
            return resolved.stdout.strip()
    raise SystemExit("Could not find dvc. Expected .venv/bin/dvc or set DVC_BIN.")


def ensure_repo_root() -> None:
    if not Path(".git").is_dir():
        raise SystemExit("Run this from the repository root.")


def load_dvc_artifacts(manifest_path: Path) -> list[DvcArtifact]:
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle)
    if not isinstance(manifest, dict):
        raise ValueError(f"{manifest_path} must contain a YAML mapping")

    artifacts = []
    for raw_artifact in manifest.get("artifacts", []):
        if not isinstance(raw_artifact, dict):
            raise ValueError("Each artifact entry must be a YAML mapping")
        artifacts.append(
            DvcArtifact(
                artifact_id=str(raw_artifact["artifact_id"]),
                path=Path(str(raw_artifact["path"])),
                artifact_type=str(raw_artifact.get("type", "")),
                source_id=str(raw_artifact.get("source_id", "")),
                dvc=bool(raw_artifact.get("dvc", False)),
            )
        )
    return artifacts


def validate_closure_dvc_overlay_anchor(
    overlay_path: Path = DEFAULT_CLOSURE_DVC_MANIFEST,
) -> None:
    """Require the post-lock overlay to extend the exact E0-P base inventory."""
    with overlay_path.open("r", encoding="utf-8") as handle:
        overlay = yaml.safe_load(handle)
    anchor = overlay.get("sealed_base_inventory") if isinstance(overlay, dict) else None
    if not isinstance(anchor, dict):
        raise ValueError(f"{overlay_path} must declare sealed_base_inventory")
    expected_anchor = {
        "path": DEFAULT_DVC_MANIFEST.as_posix(),
        "bytes": 18841,
        "sha256": "3304fd61978604ecfba5f99f1a9b3d04e4655f45f97f92954081751346143605",
        "authority": CLOSURE_PROTOCOL_LOCK_PATH.as_posix(),
    }
    if anchor != expected_anchor:
        raise ValueError(f"{overlay_path} sealed_base_inventory differs from E0-P")

    protocol_lock = json.loads(CLOSURE_PROTOCOL_LOCK_PATH.read_text(encoding="utf-8"))
    source_records = protocol_lock.get("source_artifacts") if isinstance(protocol_lock, dict) else None
    matching_records = (
        [
            record
            for record in source_records
            if isinstance(record, dict) and record.get("path") == DEFAULT_DVC_MANIFEST.as_posix()
        ]
        if isinstance(source_records, list)
        else []
    )
    if len(matching_records) != 1:
        raise ValueError("Closure protocol lock must contain the sealed base DVC inventory")
    locked_record = matching_records[0]
    if (
        locked_record.get("bytes") != anchor["bytes"]
        or locked_record.get("sha256") != anchor["sha256"]
    ):
        raise ValueError("Closure DVC overlay anchor differs from the protocol-lock source record")
    if (
        DEFAULT_DVC_MANIFEST.stat().st_size != anchor["bytes"]
        or sha256_file(DEFAULT_DVC_MANIFEST) != anchor["sha256"]
    ):
        raise ValueError("Protocol-locked base DVC inventory changed")


def load_configured_dvc_artifacts(manifest_path: Path) -> list[DvcArtifact]:
    """Load the sealed base inventory plus its derived Closure V1 overlay."""
    manifest_paths = [manifest_path]
    if manifest_path.resolve() == DEFAULT_DVC_MANIFEST.resolve():
        validate_closure_dvc_overlay_anchor()
        manifest_paths.append(DEFAULT_CLOSURE_DVC_MANIFEST)
    artifacts = [
        artifact
        for configured_path in manifest_paths
        for artifact in load_dvc_artifacts(configured_path)
    ]
    artifact_ids = [artifact.artifact_id for artifact in artifacts]
    artifact_paths = [artifact.path for artifact in artifacts]
    if len(artifact_ids) != len(set(artifact_ids)):
        raise ValueError("DVC artifact inventories contain duplicate artifact_id values")
    if len(artifact_paths) != len(set(artifact_paths)):
        raise ValueError("DVC artifact inventories contain duplicate paths")
    return artifacts


def dvc_pointer_path(path: Path) -> Path:
    if path.is_dir():
        return path.with_name(path.name + ".dvc")
    return Path(path.as_posix() + ".dvc")


def path_text(path: Path) -> str:
    return path.as_posix().rstrip("/")


def is_same_or_inside(candidate: str, parent: Path) -> bool:
    parent_text = path_text(parent)
    candidate = candidate.rstrip("/")
    return candidate == parent_text or candidate.startswith(parent_text + "/")


def is_artifact_covered(candidate: str, artifacts: list[DvcArtifact]) -> bool:
    for artifact in artifacts:
        if not artifact.dvc:
            continue
        if is_same_or_inside(candidate, artifact.path):
            return True
        if candidate == dvc_pointer_path(artifact.path).as_posix():
            return True
    return False


def has_local_dvc_pointer(candidate: Path) -> bool:
    """Return true when a path is protected by a local DVC pointer file."""
    for path in [candidate, *candidate.parents]:
        if path == Path("."):
            break
        if dvc_pointer_path(path).exists():
            return True
    return False


def collect_strings(value: Any) -> set[str]:
    strings: set[str] = set()
    if isinstance(value, str):
        strings.add(value)
    elif isinstance(value, dict):
        for key, nested in value.items():
            strings.update(collect_strings(key))
            strings.update(collect_strings(nested))
    elif isinstance(value, list):
        for nested in value:
            strings.update(collect_strings(nested))
    return strings


def dvc_status_json(dvc_bin: str) -> dict[str, Any]:
    result = run_command([dvc_bin, "status", "--json"], env=dvc_environment())
    if not result.stdout.strip():
        return {}
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        return {}
    return payload


def dvc_status_candidates(status_payload: dict[str, Any], artifacts: list[DvcArtifact]) -> list[DvcArtifact]:
    if not status_payload:
        return []
    status_strings = collect_strings(status_payload)
    candidates = []
    for artifact in artifacts:
        if not artifact.dvc or not artifact.path.exists():
            continue
        pointer = dvc_pointer_path(artifact.path).as_posix()
        for item in status_strings:
            if item == pointer or is_same_or_inside(item, artifact.path):
                candidates.append(artifact)
                break
    return sorted(set(candidates), key=lambda artifact: artifact.path.as_posix())


def declared_artifacts_missing_pointers(artifacts: list[DvcArtifact]) -> list[DvcArtifact]:
    candidates = []
    for artifact in artifacts:
        if not artifact.dvc:
            continue
        if not artifact.path.exists():
            continue
        if dvc_pointer_path(artifact.path).exists():
            continue
        candidates.append(artifact)
    return sorted(candidates, key=lambda artifact: artifact.path.as_posix())


def parse_git_status_lines(output: str) -> list[tuple[str, str]]:
    rows = []
    for line in output.splitlines():
        if len(line) < 4:
            continue
        rows.append((line[:2], line[3:]))
    return rows


def parse_git_name_status(output: str) -> list[tuple[str, Path]]:
    rows = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        rows.append((parts[0], Path(parts[-1])))
    return rows


def validate_deferred_dvc_staged_scope(staged_status: str) -> str:
    rows = parse_git_name_status(staged_status)
    observed: dict[str, str] = {}
    for status_code, path in rows:
        if status_code not in {"A", "M"} or path.as_posix() in observed:
            raise DeferredDvcTargetError(
                "Deferred models staging contains a rename, deletion, duplicate, or unknown status"
            )
        observed[path.as_posix()] = status_code
    for gate, expected_scope in _deferred_dvc_staged_scopes().items():
        if observed == expected_scope:
            return gate
    raise DeferredDvcTargetError(
        "Deferred models staging must be exact H-E0-MV/P-E0-MV, exact "
        "H-E0-MW/P-E0-MW, or current H-E0-MX 6M+5A/P-E0-MX 2A"
    )


def validate_deferred_dvc_pre_stage_scope(status_output: str) -> str:
    rows = parse_git_status_lines(status_output)
    observed: dict[str, str] = {}
    for status_code, raw_path in rows:
        if raw_path in observed:
            raise DeferredDvcTargetError(
                "Deferred models pre-stage scope contains a duplicate path"
            )
        observed[raw_path] = status_code

    def expected(scope: Mapping[str, str]) -> dict[str, str]:
        return {
            path: ("??" if staged_code == "A" else " M")
            for path, staged_code in scope.items()
        }

    for gate, expected_scope in _deferred_dvc_staged_scopes().items():
        if observed == expected(expected_scope):
            return gate
    raise DeferredDvcTargetError(
        "Deferred models pre-stage scope must be exact H-E0-MV/P-E0-MV, exact "
        "H-E0-MW/P-E0-MW, or current H-E0-MX 6M+5A/P-E0-MX 2A"
    )


def validate_deferred_dvc_staged_bindings(
    gate: str, *, repo_root: Path = Path(".")
) -> None:
    expected_modes = _deferred_dvc_git_modes().get(gate)
    expected_scope = _deferred_dvc_staged_scopes().get(gate)
    if expected_modes is None or expected_scope is None:
        raise DeferredDvcTargetError("Deferred models staged binding gate is unknown")
    staged_status = _git_output(
        repo_root, "diff", "--cached", "--name-status"
    )
    if validate_deferred_dvc_staged_scope(staged_status) != gate:
        raise DeferredDvcTargetError(
            "Deferred models staged scope changed after the initial Git add"
        )
    expected_short_status = [
        f"{status_code}  {path}"
        for path, status_code in sorted(expected_scope.items())
    ]
    observed_short_status = _git_output(
        repo_root, "status", "--short", "--untracked-files=normal"
    ).splitlines()
    if observed_short_status != expected_short_status:
        raise DeferredDvcTargetError(
            "Deferred models short Git status differs from the exact staged scope"
        )
    if _git_output(repo_root, "diff", "--name-status").strip():
        raise DeferredDvcTargetError(
            "Deferred models mode left an unstaged tracked change"
        )
    for raw_path, git_mode in sorted(expected_modes.items()):
        path = repo_root / raw_path
        _require_no_symlink_ancestors(path, anchor=repo_root)
        physical_mode = 0o755 if git_mode == "100755" else 0o644
        _require_regular_file(path, mode=physical_mode)
        index_line = _git_output(
            repo_root, "ls-files", "-s", "--", raw_path
        ).strip()
        parts = index_line.split(maxsplit=3)
        if (
            len(parts) != 4
            or parts[0] != git_mode
            or parts[2] != "0"
            or parts[3] != raw_path
        ):
            raise DeferredDvcTargetError(
                f"Deferred models staged mode/stage binding drifted: {raw_path}"
            )
        index_oid = parts[1]
        worktree_oid = _git_output(
            repo_root, "hash-object", "--no-filters", "--", raw_path
        ).strip()
        if index_oid != worktree_oid or len(index_oid) != 40:
            raise DeferredDvcTargetError(
                f"Deferred models staged blob differs from worktree: {raw_path}"
            )


def should_skip_ignored_path(path: str) -> bool:
    if path in REGENERABLE_IGNORED_PATHS:
        return True
    if any(path.startswith(prefix) for prefix in IGNORED_PREFIXES_TO_SKIP):
        return True
    if path.startswith("reports/") and path.endswith(REPORT_SMOKE_PARQUET_SUFFIXES):
        return True
    return any(part in IGNORED_PATH_PARTS_TO_SKIP for part in Path(path).parts)


def is_heavy_ignored_path(path: str) -> bool:
    if should_skip_ignored_path(path):
        return False
    if any(path.startswith(prefix) for prefix in HEAVY_PREFIXES):
        return True
    if path.startswith("reports/") and path.endswith(".parquet"):
        return True
    return path == "reports/anfis/operational_site_review_summary.csv"


def unmanaged_ignored_heavy_paths(artifacts: list[DvcArtifact]) -> list[Path]:
    result = run_command(["git", "status", "--short", "--ignored", "--untracked-files=normal"])
    paths = []
    for status, path in parse_git_status_lines(result.stdout):
        normalized = path.rstrip("/")
        if status != "!!":
            continue
        if not is_heavy_ignored_path(normalized):
            continue
        if is_artifact_covered(normalized, artifacts):
            continue
        if has_local_dvc_pointer(Path(normalized)):
            continue
        paths.append(Path(normalized))
    return sorted(set(paths), key=lambda path: path.as_posix())


def versionable_changes() -> str:
    return run_command(["git", "status", "--short", "--untracked-files=normal"]).stdout


def normalize_repo_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        return path
    repo_root = Path.cwd().resolve()
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo_root)
    except ValueError:
        return path


def is_experiment_manifest_path(path: Path) -> bool:
    text = path.as_posix()
    if path.name.endswith("_promotion_manifest.json"):
        return False
    if path in {CLOSURE_PROTOCOL_LOCK_PATH, CLOSURE_DEVELOPMENT_RUNTIME_LOCK_PATH}:
        return True
    if path.name == CLOSURE_COMMON_ORIGIN_MANIFEST_PATH.name:
        return path == CLOSURE_COMMON_ORIGIN_MANIFEST_PATH
    return text.startswith("reports/") and path.suffix == ".json" and "manifest" in path.name


def is_report_artifact_path(path: Path) -> bool:
    text = path.as_posix()
    if not text.startswith("reports/"):
        return False
    if text.startswith("reports/data/"):
        return False
    if path.name.endswith("_promotion_manifest.json"):
        return False
    if is_experiment_manifest_path(path):
        return False
    return path.suffix in REPORT_ARTIFACT_SUFFIXES


def manifest_record_path(record: Any) -> Path | None:
    if not isinstance(record, dict):
        return None
    raw_path = record.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    return normalize_repo_path(raw_path)


def record_display_path(path: Path) -> str:
    return path.as_posix() if not path.is_absolute() else str(path)


def manifest_output_records(payload: Any, manifest_path: Path) -> Any:
    if not isinstance(payload, dict):
        return None
    if manifest_path == CLOSURE_PROTOCOL_LOCK_PATH:
        return payload.get("generated_lock_companions")
    if manifest_path == CLOSURE_COMMON_ORIGIN_MANIFEST_PATH:
        return [payload.get("output")]
    return payload.get("outputs")


def validate_closure_development_runtime_lock_manifest(
    manifest_path: Path,
) -> list[ReproducibilityFinding]:
    """Validate staged E0-DL physically without claiming it is published yet."""
    from src.experiments.closure_development_runtime_lock import (
        load_and_validate_development_runtime_lock,
    )

    try:
        _, summary = load_and_validate_development_runtime_lock(
            manifest_path,
            CLOSURE_DEVELOPMENT_RUNTIME_LOCK_SCHEMA,
            require_published=False,
            require_physical_artifacts=True,
        )
    except Exception as exc:
        return [
            ReproducibilityFinding(
                "fail",
                "manifest",
                manifest_path.as_posix(),
                f"Closure E0-DL validation failed: {exc}",
            )
        ]

    expected = {
        "lock_version": CLOSURE_DEVELOPMENT_RUNTIME_LOCK_VERSION,
        "status": "locked",
        "publication_verified": False,
        "physical_artifacts_verified": True,
        "canonical_origin_identity_verified": True,
        "dvc_remote_verified_at_lock": True,
        "dvc_remote_verified": True,
        "locked_parent_published_at_lock": True,
        "payload_development_fit_authorized": True,
        "development_fit_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "fit_authorized": False,
        "future_outcomes_accessed": False,
    }
    drift = {
        key: {"observed": summary.get(key), "expected": value}
        for key, value in expected.items()
        if summary.get(key) != value
    }
    if drift:
        return [
            ReproducibilityFinding(
                "fail",
                "manifest",
                manifest_path.as_posix(),
                f"Closure E0-DL authorization summary drifted: {drift}.",
            )
        ]
    return [
        ReproducibilityFinding(
            "ok",
            "manifest",
            manifest_path.as_posix(),
            "Closure E0-DL schema, hashes, ancestry, DVC ownership, and seals passed pre-publication validation.",
        )
    ]


def validate_closure_expert_state_manifest(
    manifest_path: Path,
) -> list[ReproducibilityFinding]:
    """Run the exact, outcome-free expert bundle and Parquet semantic audit."""
    from src.experiments.closure_contract import load_yaml_mapping
    from src.experiments.closure_development_runtime_lock import (
        expert_state_lock_record,
    )
    from src.experiments.closure_runtime_contract import DEFAULT_RUNTIME_CONFIG

    try:
        runtime = load_yaml_mapping(DEFAULT_RUNTIME_CONFIG)
        record = expert_state_lock_record(runtime, require_physical_artifact=True)
        completion_paths = {
            item.get("path")
            for item in record["completion_records"]
            if isinstance(item, Mapping)
        }
        if manifest_path.as_posix() not in completion_paths:
            raise ValueError("exact expert-state manifest path is absent from the bundle")
    except Exception as exc:
        return [
            ReproducibilityFinding(
                "fail",
                "manifest",
                manifest_path.as_posix(),
                f"Closure expert-state validation failed: {exc}",
            )
        ]
    return [
        ReproducibilityFinding(
            "ok",
            "manifest",
            manifest_path.as_posix(),
            (
                "Closure expert-state provenance, explicit DVC pointer, lineage, "
                "and outcome-free Parquet semantic audit passed."
            ),
        )
    ]


def verify_manifest_file_record(
    *,
    record: Any,
    manifest_path: Path,
    section: str,
    findings: list[ReproducibilityFinding],
    max_hash_bytes: int,
    require_hash: bool,
    force_hash: bool = False,
) -> Path | None:
    record_path = manifest_record_path(record)
    if record_path is None:
        findings.append(
            ReproducibilityFinding(
                "fail",
                "manifest",
                manifest_path.as_posix(),
                f"{section} record is missing a valid path.",
            )
        )
        return None

    actual_path = record_path
    display_path = record_display_path(record_path)
    if not actual_path.exists():
        findings.append(
            ReproducibilityFinding(
                "fail",
                "manifest",
                display_path,
                f"{manifest_path} lists this {section} path, but it does not exist.",
            )
        )
        return record_path

    if isinstance(record, dict):
        if actual_path.is_dir():
            actual_bytes, actual_sha = sha256_directory(actual_path)
        else:
            actual_bytes = actual_path.stat().st_size
            actual_sha = None

        expected_bytes = record.get("bytes")
        if isinstance(expected_bytes, int):
            if actual_bytes != expected_bytes:
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        display_path,
                        f"{section} byte count changed: manifest={expected_bytes}, current={actual_bytes}.",
                    )
                )

        expected_sha = record.get("sha256")
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "manifest",
                    display_path,
                    f"{section} record is missing a 64-character SHA-256 hash.",
                )
            )
            return record_path

        should_hash = force_hash or (require_hash and actual_bytes <= max_hash_bytes)
        if should_hash:
            actual_sha = actual_sha or sha256_file(actual_path)
            if actual_sha != expected_sha:
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        display_path,
                        f"{section} SHA-256 changed: manifest={expected_sha}, current={actual_sha}.",
                    )
                )
        elif require_hash:
            findings.append(
                ReproducibilityFinding(
                    "warn",
                    "manifest",
                    display_path,
                    (
                        f"{section} is {actual_bytes} bytes, above --max-manifest-hash-bytes="
                        f"{max_hash_bytes}; byte count was checked, SHA-256 was not recomputed."
                    ),
                )
            )

    return record_path


def discover_relevant_manifest_paths(staged_paths: set[Path]) -> list[Path]:
    manifest_paths = {path for path in staged_paths if is_experiment_manifest_path(path)}
    if dvc_pointer_path(CLOSURE_COMMON_ORIGIN_OUTPUT_PATH) in staged_paths:
        manifest_paths.add(CLOSURE_COMMON_ORIGIN_MANIFEST_PATH)
    if dvc_pointer_path(CLOSURE_EXPERT_STATE_OUTPUT_PATH) in staged_paths:
        manifest_paths.add(CLOSURE_EXPERT_STATE_MANIFEST_PATH)
    for path in staged_paths:
        if not is_report_artifact_path(path):
            continue
        if not path.parent.exists():
            continue
        candidates = set(path.parent.glob("*manifest*.json"))
        closure_lock_candidate = path.parent / CLOSURE_PROTOCOL_LOCK_PATH.name
        if closure_lock_candidate == CLOSURE_PROTOCOL_LOCK_PATH and closure_lock_candidate.exists():
            candidates.add(closure_lock_candidate)
        for candidate in candidates:
            if not is_experiment_manifest_path(candidate):
                continue
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            outputs = manifest_output_records(payload, candidate)
            if not isinstance(outputs, list):
                continue
            output_paths = {record_path for record in outputs if (record_path := manifest_record_path(record)) is not None}
            if path in output_paths:
                manifest_paths.add(candidate)
    return sorted(manifest_paths, key=lambda path: path.as_posix())


def _canonical_json_sha256(value: Any) -> str | None:
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(payload).hexdigest()


def validate_closure_mifal_development_manifest(
    payload: Any,
    manifest_path: Path,
) -> list[ReproducibilityFinding]:
    """Validate the exact manifest-last M0 dialect without rewriting it."""
    findings: list[ReproducibilityFinding] = []

    def fail(message: str) -> None:
        findings.append(
            ReproducibilityFinding(
                "fail",
                "manifest",
                manifest_path.as_posix(),
                message,
            )
        )

    if manifest_path != CLOSURE_MIFAL_DEVELOPMENT_MANIFEST_PATH:
        fail("Closure M0 manifest compatibility is restricted to its exact path.")
        return findings
    if not isinstance(payload, dict):
        fail("Closure M0 manifest must contain a JSON object.")
        return findings

    expected_top_level = {
        "schema_version",
        "experiment_id",
        "surface_id",
        "model_id",
        "gate",
        "status",
        "started_at_utc",
        "counts",
        "raw_prediction_contract",
        "model_spec_sha256",
        "lineage_audit_sha256",
        "runtime_versions",
        "effective_authority",
        "inputs",
        "script",
        "source_code",
        "outputs",
        "manifest_written_last",
        *CLOSURE_MIFAL_MANIFEST_FALSE_FLAGS,
        "outcome_access_log_state",
        "completion_marker_written_last",
    }
    if set(payload) != expected_top_level:
        fail("Closure M0 manifest top-level dialect drifted.")
    if (
        payload.get("schema_version")
        != CLOSURE_MIFAL_DEVELOPMENT_MANIFEST_SCHEMA_VERSION
        or payload.get("experiment_id") != "closure_v1"
        or payload.get("surface_id")
        != "closure_v1_wqp_adaptive_no_current_chla"
        or payload.get("model_id") != "M0"
        or payload.get("gate") != "E0-MR"
        or payload.get("status") != CLOSURE_MIFAL_DEVELOPMENT_MANIFEST_STATUS
    ):
        fail("Closure M0 manifest identity/schema/status drifted.")

    started_at = payload.get("started_at_utc")
    try:
        parsed_started_at = datetime.fromisoformat(started_at)
    except (TypeError, ValueError):
        parsed_started_at = None
    if (
        parsed_started_at is None
        or not isinstance(started_at, str)
        or not started_at.endswith("+00:00")
        or parsed_started_at.tzinfo is None
    ):
        fail("Closure M0 manifest UTC start timestamp is invalid.")
    if payload.get("counts") != CLOSURE_MIFAL_EXPECTED_COUNTS:
        fail("Closure M0 manifest denominators drifted.")

    raw_contract = payload.get("raw_prediction_contract")
    if (
        not isinstance(raw_contract, dict)
        or _canonical_json_sha256(raw_contract)
        != CLOSURE_MIFAL_RAW_PREDICTION_CONTRACT_SHA256
    ):
        fail("Closure M0 exact 28-column raw prediction contract drifted.")
    expected_authority = {
        **CLOSURE_MIFAL_EXPECTED_AUTHORITY,
        "raw_prediction_contract": raw_contract,
    }
    if payload.get("effective_authority") != expected_authority:
        fail("Closure M0 effective E0-MR authority drifted.")

    runtime_versions = payload.get("runtime_versions")
    if (
        not isinstance(runtime_versions, dict)
        or set(runtime_versions)
        != {
            "python",
            "numpy",
            "pandas",
            "pyarrow",
            "threadpoolctl",
            "threadpool_limit",
            "mifal_core",
        }
        or any(
            not isinstance(runtime_versions.get(name), str)
            or not runtime_versions[name]
            for name in (
                "python",
                "numpy",
                "pandas",
                "pyarrow",
                "threadpoolctl",
            )
        )
        or runtime_versions.get("threadpool_limit") != 1
        or runtime_versions.get("mifal_core") != "5.0.0"
    ):
        fail("Closure M0 runtime-version record drifted.")

    inputs = payload.get("inputs")
    input_by_path: dict[Path, dict[str, Any]] = {}
    expected_input_bindings = [
        (path.as_posix(), role)
        for path, role in CLOSURE_MIFAL_DEVELOPMENT_INPUT_PATHS_AND_ROLES
    ]
    if not isinstance(inputs, list) or len(inputs) != len(expected_input_bindings):
        fail("Closure M0 manifest must bind exactly 28 inputs.")
    else:
        observed_input_bindings: list[tuple[str, str]] = []
        valid_inputs = True
        for raw_record in inputs:
            if not isinstance(raw_record, dict):
                valid_inputs = False
                continue
            record = cast(dict[str, Any], raw_record)
            path = record.get("path")
            role = record.get("artifact_role")
            sha256 = record.get("sha256")
            if (
                set(record) != {"path", "bytes", "sha256", "artifact_role"}
                or not isinstance(path, str)
                or not isinstance(role, str)
                or type(record.get("bytes")) is not int
                or record["bytes"] < 1
                or not isinstance(sha256, str)
                or len(sha256) != 64
                or any(character not in "0123456789abcdef" for character in sha256)
            ):
                valid_inputs = False
                continue
            observed_input_bindings.append((path, role))
            input_by_path[Path(path)] = record
        if (
            not valid_inputs
            or observed_input_bindings != expected_input_bindings
            or len(input_by_path) != len(expected_input_bindings)
        ):
            fail("Closure M0 input paths, roles, order, or record dialect drifted.")

    script = payload.get("script")
    if (
        CLOSURE_MIFAL_DEVELOPMENT_SCRIPT not in input_by_path
        or script != input_by_path.get(CLOSURE_MIFAL_DEVELOPMENT_SCRIPT)
    ):
        fail("Closure M0 generating script is not the exact bound runner input.")
    source_code = payload.get("source_code")
    if (
        not isinstance(source_code, list)
        or len(source_code) != len(CLOSURE_MIFAL_DEVELOPMENT_SOURCE_PATHS)
        or [manifest_record_path(record) for record in source_code]
        != list(CLOSURE_MIFAL_DEVELOPMENT_SOURCE_PATHS)
        or any(
            record != input_by_path.get(path)
            for record, path in zip(
                source_code,
                CLOSURE_MIFAL_DEVELOPMENT_SOURCE_PATHS,
                strict=True,
            )
        )
    ):
        fail("Closure M0 source-code triplet drifted from its bound inputs.")

    outputs = payload.get("outputs")
    output_by_path: dict[Path, dict[str, Any]] = {}
    if (
        not isinstance(outputs, list)
        or len(outputs) != len(CLOSURE_MIFAL_DEVELOPMENT_OUTPUT_PATHS)
    ):
        fail("Closure M0 manifest must bind exactly five pre-manifest outputs.")
    else:
        valid_outputs = True
        for raw_record in outputs:
            if not isinstance(raw_record, dict):
                valid_outputs = False
                continue
            record = cast(dict[str, Any], raw_record)
            path = manifest_record_path(record)
            sha256 = record.get("sha256")
            if (
                set(record) != {"path", "bytes", "sha256"}
                or path is None
                or type(record.get("bytes")) is not int
                or record["bytes"] < 1
                or not isinstance(sha256, str)
                or len(sha256) != 64
                or any(character not in "0123456789abcdef" for character in sha256)
            ):
                valid_outputs = False
                continue
            output_by_path[path] = record
        if (
            not valid_outputs
            or [manifest_record_path(record) for record in outputs]
            != list(CLOSURE_MIFAL_DEVELOPMENT_OUTPUT_PATHS)
            or len(output_by_path) != len(CLOSURE_MIFAL_DEVELOPMENT_OUTPUT_PATHS)
        ):
            fail("Closure M0 output paths, order, or record dialect drifted.")

    model_spec_path = CLOSURE_MIFAL_DEVELOPMENT_OUTPUT_PATHS[1]
    lineage_path = CLOSURE_MIFAL_DEVELOPMENT_OUTPUT_PATHS[2]
    if (
        payload.get("model_spec_sha256")
        != output_by_path.get(model_spec_path, {}).get("sha256")
        or payload.get("lineage_audit_sha256")
        != output_by_path.get(lineage_path, {}).get("sha256")
    ):
        fail("Closure M0 model-spec/lineage cross-hashes drifted.")

    if payload.get("manifest_written_last") is not True:
        fail("Closure M0 manifest must record manifest_written_last=true.")
    for field in CLOSURE_MIFAL_MANIFEST_FALSE_FLAGS:
        if payload.get(field) is not False:
            fail(f"Closure M0 manifest requires `{field}=false`.")
    if payload.get("outcome_access_log_state") != "absent":
        fail("Closure M0 outcome-access log state must remain absent.")
    if (
        tuple(payload)[-1:] != ("completion_marker_written_last",)
        or payload.get("completion_marker_written_last") is not True
    ):
        fail("Closure M0 completion marker must be the true final top-level key.")

    if findings:
        return findings
    return [
        ReproducibilityFinding(
            "ok",
            "manifest",
            manifest_path.as_posix(),
            (
                "Closure M0 schema, E0-MR authority, 28 inputs, three source "
                "records, five outputs, cross-hashes, and manifest-last seals passed."
            ),
        )
    ]


def validate_experiment_manifests(
    *,
    staged_paths: set[Path],
    artifacts: list[DvcArtifact],
    max_hash_bytes: int,
    verify_manifest_inputs: bool,
) -> list[ReproducibilityFinding]:
    findings: list[ReproducibilityFinding] = []
    report_artifacts = sorted(
        {path for path in staged_paths if is_report_artifact_path(path)},
        key=lambda path: path.as_posix(),
    )
    manifest_paths = discover_relevant_manifest_paths(staged_paths)
    covered_outputs: dict[Path, list[Path]] = {}
    checked_outputs = 0

    if not report_artifacts and not manifest_paths:
        return [
            ReproducibilityFinding(
                "ok",
                "manifest",
                "-",
                "No staged report artifacts require experiment-manifest validation.",
            )
        ]

    for manifest_path in manifest_paths:
        if not manifest_path.exists():
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "manifest",
                    manifest_path.as_posix(),
                    "Experiment manifest is referenced by staged reports but does not exist.",
                )
            )
            continue

        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "manifest",
                    manifest_path.as_posix(),
                    f"Experiment manifest is not valid JSON: {exc}.",
                )
            )
            continue

        is_closure_protocol_lock = manifest_path == CLOSURE_PROTOCOL_LOCK_PATH
        is_closure_development_runtime_lock = (
            manifest_path == CLOSURE_DEVELOPMENT_RUNTIME_LOCK_PATH
        )
        is_closure_common_origin_manifest = (
            manifest_path == CLOSURE_COMMON_ORIGIN_MANIFEST_PATH
        )
        is_closure_expert_state_manifest = (
            manifest_path == CLOSURE_EXPERT_STATE_MANIFEST_PATH
        )
        is_closure_mifal_development_manifest = (
            manifest_path == CLOSURE_MIFAL_DEVELOPMENT_MANIFEST_PATH
        )
        if is_closure_development_runtime_lock:
            findings.extend(
                validate_closure_development_runtime_lock_manifest(manifest_path)
            )
            continue
        if is_closure_expert_state_manifest:
            findings.extend(validate_closure_expert_state_manifest(manifest_path))
        if is_closure_protocol_lock:
            lock_version = payload.get("lock_version") if isinstance(payload, dict) else None
            status = payload.get("status") if isinstance(payload, dict) else None
            if lock_version != CLOSURE_PROTOCOL_LOCK_VERSION:
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        (
                            f"Closure protocol lock version is `{lock_version}`, "
                            f"expected `{CLOSURE_PROTOCOL_LOCK_VERSION}`."
                        ),
                    )
                )
            if status != "locked":
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        f"Closure protocol lock status is `{status}`, expected `locked`.",
                    )
                )
            for field in (
                "future_outcomes_accessed",
                "lock_command_semantically_decodes_post_2021_outcomes",
                "holdout_assignment_created",
            ):
                value = payload.get(field) if isinstance(payload, dict) else None
                if value is not False:
                    findings.append(
                        ReproducibilityFinding(
                            "fail",
                            "manifest",
                            manifest_path.as_posix(),
                            f"Closure protocol lock requires `{field}=false`.",
                        )
                    )
            locked_repository = payload.get("locked_repository") if isinstance(payload, dict) else None
            if (
                not isinstance(locked_repository, dict)
                or locked_repository.get("worktree_status") != "clean"
                or locked_repository.get("dirty_paths") != []
            ):
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        "Closure protocol lock must record a clean repository with no dirty paths.",
                    )
                )
        elif is_closure_common_origin_manifest:
            if not isinstance(payload, dict):
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        "Closure common-origin manifest must contain a JSON object.",
                    )
                )
            else:
                manifest_version = payload.get("manifest_version")
                if manifest_version != CLOSURE_COMMON_ORIGIN_MANIFEST_VERSION:
                    findings.append(
                        ReproducibilityFinding(
                            "fail",
                            "manifest",
                            manifest_path.as_posix(),
                            (
                                f"Closure common-origin manifest version is `{manifest_version}`, "
                                f"expected `{CLOSURE_COMMON_ORIGIN_MANIFEST_VERSION}`."
                            ),
                        )
                    )
                for field, expected in (
                    ("status", "completed"),
                    ("experiment_id", "closure_v1"),
                    ("surface_id", "closure_v1_wqp_adaptive_no_current_chla"),
                    ("future_outcomes_accessed", False),
                    ("target_values_projected", []),
                    ("target_parquet_semantically_opened", False),
                    ("post_cutoff_target_rows_materialized", 0),
                    ("target_availability_used_for_origin_selection", False),
                    ("availability_join", "left_after_intent_freeze"),
                ):
                    value = payload.get(field)
                    matches = value == expected
                    if expected is False:
                        matches = value is False
                    elif field == "post_cutoff_target_rows_materialized":
                        matches = type(value) is int and value == 0
                    if not matches:
                        findings.append(
                            ReproducibilityFinding(
                                "fail",
                                "manifest",
                                manifest_path.as_posix(),
                                (
                                    "Closure common-origin manifest requires "
                                    f"`{field}={json.dumps(expected)}`."
                                ),
                            )
                        )
                execution = payload.get("execution")
                repository = execution.get("repository") if isinstance(execution, dict) else None
                base_head = repository.get("base_head") if isinstance(repository, dict) else None
                status = (
                    repository.get("tracked_worktree_status")
                    if isinstance(repository, dict)
                    else None
                )
                status_lines = (
                    repository.get("tracked_status_lines")
                    if isinstance(repository, dict)
                    else None
                )
                valid_head = (
                    isinstance(base_head, str)
                    and len(base_head) in {40, 64}
                    and set(base_head).issubset(set("0123456789abcdef"))
                )
                valid_status = (
                    status in {"clean", "dirty"}
                    and isinstance(status_lines, list)
                    and all(isinstance(line, str) and line for line in status_lines)
                    and status == ("dirty" if status_lines else "clean")
                )
                if (
                    not isinstance(execution, dict)
                    or set(execution)
                    != {
                        "repository",
                        "source_tree_identity",
                        "reproduction_command",
                        "future_outcomes_semantically_decoded",
                    }
                    or not isinstance(repository, dict)
                    or set(repository)
                    != {
                        "base_head",
                        "base_head_is_complete_source_identity",
                        "tracked_worktree_status",
                        "tracked_status_lines",
                    }
                    or not valid_head
                    or repository.get("base_head_is_complete_source_identity") is not False
                    or not valid_status
                    or execution.get("source_tree_identity")
                    != "code_config_parent_sha256_records"
                    or execution.get("future_outcomes_semantically_decoded") is not False
                    or execution.get("reproduction_command")
                    != CLOSURE_COMMON_ORIGIN_REPRODUCTION_COMMAND
                ):
                    findings.append(
                        ReproducibilityFinding(
                            "fail",
                            "manifest",
                            manifest_path.as_posix(),
                            "Closure common-origin manifest has an invalid sealed execution record.",
                        )
                    )
        elif is_closure_mifal_development_manifest:
            findings.extend(
                validate_closure_mifal_development_manifest(payload, manifest_path)
            )
        elif isinstance(payload, dict) and payload.get("status") not in {None, "completed"}:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "manifest",
                    manifest_path.as_posix(),
                    f"Experiment manifest status is `{payload.get('status')}`, expected `completed`.",
                )
            )

        outputs = manifest_output_records(payload, manifest_path)
        if not isinstance(outputs, list) or not outputs:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "manifest",
                    manifest_path.as_posix(),
                    "Experiment manifest must contain a non-empty `outputs` list.",
                )
            )
            continue

        if is_closure_common_origin_manifest:
            output_paths = tuple(manifest_record_path(record) for record in outputs)
            if output_paths != (CLOSURE_COMMON_ORIGIN_OUTPUT_PATH,):
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        (
                            "Closure common-origin manifest must contain exactly the output "
                            f"`{CLOSURE_COMMON_ORIGIN_OUTPUT_PATH}`."
                        ),
                    )
                )

        for record in outputs:
            record_path = verify_manifest_file_record(
                record=record,
                manifest_path=manifest_path,
                section="output",
                findings=findings,
                max_hash_bytes=max_hash_bytes,
                require_hash=True,
                force_hash=(
                    is_closure_common_origin_manifest
                    or is_closure_expert_state_manifest
                    or is_closure_mifal_development_manifest
                ),
            )
            if record_path is not None:
                covered_outputs.setdefault(record_path, []).append(manifest_path)
                checked_outputs += 1

        if is_closure_protocol_lock:
            protocol_components = payload.get("protocol_components") if isinstance(payload, dict) else None
            source_artifacts = payload.get("source_artifacts") if isinstance(payload, dict) else None
            lock_scripts = (
                [
                    record
                    for record in protocol_components
                    if manifest_record_path(record) == CLOSURE_PROTOCOL_LOCK_SCRIPT
                ]
                if isinstance(protocol_components, list)
                else []
            )
            if len(lock_scripts) != 1:
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        "Closure protocol lock must contain exactly one generating-script record.",
                    )
                )
            script = lock_scripts[0] if len(lock_scripts) == 1 else None
            if not isinstance(protocol_components, list) or not isinstance(source_artifacts, list):
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        "Closure protocol lock must contain protocol-components and source-artifacts lists.",
                    )
                )
                inputs: Any = []
            else:
                inputs = [*protocol_components, *source_artifacts]
        elif is_closure_common_origin_manifest:
            code = payload.get("code") if isinstance(payload, dict) else None
            configs = payload.get("configs") if isinstance(payload, dict) else None
            source_inputs = payload.get("source_inputs") if isinstance(payload, dict) else None
            parent_artifacts = payload.get("parent_artifacts") if isinstance(payload, dict) else None
            common_origin_sections = (
                ("code", code, CLOSURE_COMMON_ORIGIN_CODE_PATHS),
                ("configs", configs, CLOSURE_COMMON_ORIGIN_CONFIG_PATHS),
                ("source_inputs", source_inputs, CLOSURE_COMMON_ORIGIN_SOURCE_PATHS),
                (
                    "parent_artifacts",
                    parent_artifacts,
                    tuple(path for path, _ in CLOSURE_COMMON_ORIGIN_PARENT_PATHS_AND_ROLES),
                ),
            )
            inputs = []
            for section_name, records, expected_paths in common_origin_sections:
                if not isinstance(records, list) or not records:
                    findings.append(
                        ReproducibilityFinding(
                            "fail",
                            "manifest",
                            manifest_path.as_posix(),
                            (
                                "Closure common-origin manifest must contain a non-empty "
                                f"`{section_name}` list."
                            ),
                        )
                    )
                    continue
                observed_paths = tuple(manifest_record_path(record) for record in records)
                if observed_paths != expected_paths:
                    findings.append(
                        ReproducibilityFinding(
                            "fail",
                            "manifest",
                            manifest_path.as_posix(),
                            (
                                f"Closure common-origin `{section_name}` paths must equal "
                                f"{[path.as_posix() for path in expected_paths]}."
                            ),
                        )
                    )
                inputs.extend(records)

            if isinstance(source_inputs, list):
                for raw_record, expected_role in zip(
                    source_inputs,
                    CLOSURE_COMMON_ORIGIN_SOURCE_ROLES,
                    strict=False,
                ):
                    record = cast(dict[str, Any], raw_record) if isinstance(raw_record, dict) else None
                    if (
                        record is None
                        or record.get("role") != expected_role
                        or record.get("hash_source") != "protocol_lock"
                    ):
                        findings.append(
                            ReproducibilityFinding(
                                "fail",
                                "manifest",
                                manifest_path.as_posix(),
                                "Closure common-origin source roles/hash_source are invalid.",
                            )
                        )
                        break

            if isinstance(parent_artifacts, list):
                for raw_record, (_, expected_role) in zip(
                    parent_artifacts,
                    CLOSURE_COMMON_ORIGIN_PARENT_PATHS_AND_ROLES,
                    strict=False,
                ):
                    record = cast(dict[str, Any], raw_record) if isinstance(raw_record, dict) else None
                    if record is None or record.get("role") != expected_role:
                        findings.append(
                            ReproducibilityFinding(
                                "fail",
                                "manifest",
                                manifest_path.as_posix(),
                                "Closure common-origin parent roles are invalid.",
                            )
                        )
                        break

            assignment = payload.get("assignment") if isinstance(payload, dict) else None
            assignment_parent = (
                parent_artifacts[2]
                if isinstance(parent_artifacts, list) and len(parent_artifacts) == 3
                else None
            )
            if (
                not isinstance(assignment, dict)
                or assignment.get("path")
                != CLOSURE_COMMON_ORIGIN_PARENT_PATHS_AND_ROLES[2][0].as_posix()
                or type(assignment.get("bytes")) is not int
                or assignment.get("bytes", -1) < 0
                or not isinstance(assignment.get("sha256"), str)
                or assignment.get("eligible_locations") != 441
                or assignment.get("development_locations") != 353
                or assignment.get("holdout_locations") != 88
                or assignment.get("holdout_fit_overlap_count") != 0
                or not isinstance(assignment_parent, dict)
                or assignment_parent.get("bytes") != assignment.get("bytes")
                or assignment_parent.get("sha256") != assignment.get("sha256")
            ):
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        "Closure common-origin assignment provenance is invalid.",
                    )
                )

            generating_scripts = (
                [
                    record
                    for record in code
                    if manifest_record_path(record)
                    == CLOSURE_COMMON_ORIGIN_MANIFEST_SCRIPT
                ]
                if isinstance(code, list)
                else []
            )
            if len(generating_scripts) != 1:
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "manifest",
                        manifest_path.as_posix(),
                        (
                            "Closure common-origin manifest must contain exactly one "
                            "generating-script record for "
                            f"`{CLOSURE_COMMON_ORIGIN_MANIFEST_SCRIPT}`."
                        ),
                    )
                )
            script = generating_scripts[0] if len(generating_scripts) == 1 else None
        elif is_closure_expert_state_manifest:
            script = payload.get("script") if isinstance(payload, dict) else None
            expert_inputs = payload.get("inputs") if isinstance(payload, dict) else None
            expert_dependencies = (
                payload.get("dependencies") if isinstance(payload, dict) else None
            )
            inputs = (
                [*expert_inputs, *expert_dependencies]
                if isinstance(expert_inputs, list)
                and isinstance(expert_dependencies, list)
                else None
            )
        else:
            script = payload.get("script") if isinstance(payload, dict) else None
            inputs = payload.get("inputs") if isinstance(payload, dict) else None

        if isinstance(script, dict):
            verify_manifest_file_record(
                record=script,
                manifest_path=manifest_path,
                section="script",
                findings=findings,
                max_hash_bytes=max_hash_bytes,
                require_hash=True,
                force_hash=True,
            )
        elif not is_closure_protocol_lock and not is_closure_common_origin_manifest:
            findings.append(
                ReproducibilityFinding(
                    "warn",
                    "manifest",
                    manifest_path.as_posix(),
                    "Experiment manifest does not record the generating script.",
                )
            )

        if isinstance(inputs, list):
            for record in inputs:
                verify_manifest_file_record(
                    record=record,
                    manifest_path=manifest_path,
                    section="input",
                    findings=findings,
                    max_hash_bytes=max_hash_bytes,
                    require_hash=(
                        verify_manifest_inputs
                        or is_closure_common_origin_manifest
                        or is_closure_expert_state_manifest
                        or is_closure_mifal_development_manifest
                    ),
                    force_hash=(
                        is_closure_common_origin_manifest
                        or is_closure_expert_state_manifest
                        or is_closure_mifal_development_manifest
                    ),
                )
        elif inputs is None:
            findings.append(
                ReproducibilityFinding(
                    "warn",
                    "manifest",
                    manifest_path.as_posix(),
                    "Experiment manifest does not record inputs.",
                )
            )
        else:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "manifest",
                    manifest_path.as_posix(),
                    "Experiment manifest `inputs` field must be a list when present.",
                )
            )

    for path in report_artifacts:
        if path not in covered_outputs:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "manifest",
                    path.as_posix(),
                    "Staged report artifact is not listed in any experiment manifest output.",
                )
            )

    staged_dvc_outputs = [
        path
        for path in covered_outputs
        if is_artifact_covered(path.as_posix(), artifacts) and dvc_pointer_path(path).exists()
    ]
    findings.append(
        ReproducibilityFinding(
            "ok",
            "manifest",
            "-",
            (
                f"Checked {len(manifest_paths)} experiment manifest(s), {checked_outputs} output record(s), "
                f"and {len(report_artifacts)} staged report artifact(s). "
                f"{len(staged_dvc_outputs)} covered output(s) are also protected by DVC pointers."
            ),
        )
    )
    return findings


def validate_dvc_pointers(staged_paths: set[Path], selected_dvc_paths: list[Path]) -> list[ReproducibilityFinding]:
    findings: list[ReproducibilityFinding] = []
    pointer_paths = {path for path in staged_paths if path.suffix == ".dvc"}
    pointer_paths.update(dvc_pointer_path(path) for path in selected_dvc_paths)

    if not pointer_paths:
        return [ReproducibilityFinding("ok", "dvc", "-", "No DVC pointer files need pointer-structure validation.")]

    for pointer_path in sorted(pointer_paths, key=lambda path: path.as_posix()):
        if not pointer_path.exists():
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "dvc",
                    pointer_path.as_posix(),
                    "Expected DVC pointer file does not exist.",
                )
            )
            continue
        try:
            payload = yaml.safe_load(pointer_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "dvc",
                    pointer_path.as_posix(),
                    f"DVC pointer is not valid YAML: {exc}.",
                )
            )
            continue
        outs = payload.get("outs") if isinstance(payload, dict) else None
        if not isinstance(outs, list) or not outs:
            findings.append(
                ReproducibilityFinding(
                    "fail",
                    "dvc",
                    pointer_path.as_posix(),
                    "DVC pointer must contain a non-empty `outs` list.",
                )
            )
            continue
        for out in outs:
            if not isinstance(out, dict) or not out.get("path") or not out.get("md5"):
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "dvc",
                        pointer_path.as_posix(),
                        "Each DVC pointer output must include `path` and `md5`.",
                    )
                )
                break

    if not any(finding.level == "fail" and finding.check == "dvc" for finding in findings):
        findings.append(
            ReproducibilityFinding(
                "ok",
                "dvc",
                "-",
                f"Validated {len(pointer_paths)} DVC pointer file(s).",
            )
        )
    return findings


def is_freeze_sensitive_path(path: Path) -> bool:
    text = path.as_posix()
    if path in FREEZE_ARTIFACT_PATHS:
        return False
    if text in FREEZE_SENSITIVE_EXACT_PATHS:
        return True
    return any(text.startswith(prefix) for prefix in FREEZE_SENSITIVE_PREFIXES)


def validate_freeze_freshness(staged_rows: list[tuple[str, Path]]) -> list[ReproducibilityFinding]:
    changed_paths = {path for _, path in staged_rows}
    sensitive_paths = sorted(
        {path for path in changed_paths if is_freeze_sensitive_path(path)},
        key=lambda path: path.as_posix(),
    )
    changed_freeze_outputs = changed_paths.intersection(FREEZE_REQUIRED_OUTPUTS)
    freeze_documentation_only = (
        sensitive_paths == [Path("src/data/freeze.py")]
        and bool(changed_freeze_outputs)
        and changed_freeze_outputs.issubset(FREEZE_DOCUMENTATION_OUTPUTS)
    )
    findings: list[ReproducibilityFinding] = []

    if sensitive_paths:
        if freeze_documentation_only:
            findings.append(
                ReproducibilityFinding(
                    "ok",
                    "freeze",
                    "src/data/freeze.py",
                    "Freeze generator documentation changes are paired with freeze Markdown/JSON metadata; derived file hashes are not required.",
                )
            )
        else:
            missing_freeze_outputs = sorted(FREEZE_REQUIRED_OUTPUTS - changed_paths, key=lambda path: path.as_posix())
            if missing_freeze_outputs:
                findings.append(
                    ReproducibilityFinding(
                        "fail",
                        "freeze",
                        ", ".join(path.as_posix() for path in sensitive_paths[:5]),
                        (
                            "Freeze-sensitive data pipeline changes are staged, but not all required "
                            f"freeze outputs are staged: {', '.join(path.as_posix() for path in missing_freeze_outputs)}."
                        ),
                    )
                )
            else:
                findings.append(
                    ReproducibilityFinding(
                        "ok",
                        "freeze",
                        "-",
                        f"Freeze-sensitive changes are paired with {len(FREEZE_REQUIRED_OUTPUTS)} required freeze outputs.",
                    )
                )
    else:
        findings.append(
            ReproducibilityFinding(
                "ok",
                "freeze",
                "-",
                "No freeze-sensitive data pipeline changes are staged.",
            )
        )

    if changed_freeze_outputs and changed_freeze_outputs != FREEZE_REQUIRED_OUTPUTS and not freeze_documentation_only:
        findings.append(
            ReproducibilityFinding(
                "fail",
                "freeze",
                ", ".join(path.as_posix() for path in sorted(changed_freeze_outputs, key=lambda path: path.as_posix())),
                "A data-freeze update must stage derived CSV, JSON manifest, and DATA_FREEZE.md together.",
            )
        )

    if DEFAULT_DVC_ARTIFACT_INVENTORY in changed_paths and not sensitive_paths:
        findings.append(
            ReproducibilityFinding(
                "ok",
                "freeze",
                DEFAULT_DVC_ARTIFACT_INVENTORY.as_posix(),
                (
                    "DVC artifact inventory changed, but no freeze-sensitive data pipeline paths "
                    "are staged; data-freeze regeneration is not required by this check."
                ),
            )
        )

    return findings


def reproducibility_checks(
    *,
    staged_status: str,
    selected_dvc_paths: list[Path],
    artifacts: list[DvcArtifact],
    max_manifest_hash_bytes: int,
    verify_manifest_inputs: bool,
) -> list[ReproducibilityFinding]:
    staged_rows = parse_git_name_status(staged_status)
    staged_paths = {path for status, path in staged_rows if not status.startswith("D")}
    findings: list[ReproducibilityFinding] = []
    findings.extend(validate_dvc_pointers(staged_paths, selected_dvc_paths))
    findings.extend(
        validate_experiment_manifests(
            staged_paths=staged_paths,
            artifacts=artifacts,
            max_hash_bytes=max_manifest_hash_bytes,
            verify_manifest_inputs=verify_manifest_inputs,
        )
    )
    findings.extend(validate_freeze_freshness(staged_rows))
    return findings


def has_failing_findings(findings: list[ReproducibilityFinding]) -> bool:
    return any(finding.level == "fail" for finding in findings)


def prompt_yes_no(question: str, *, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        answer = input(f"{question} {suffix} ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please answer yes or no.")


def print_artifact_table(title: str, artifacts: list[DvcArtifact]) -> None:
    print()
    print(title)
    if not artifacts:
        print("  none")
        return
    for artifact in artifacts:
        print(f"  - {artifact.path} ({artifact.artifact_id}, {artifact.artifact_type})")


def print_path_table(title: str, paths: list[Path]) -> None:
    print()
    print(title)
    if not paths:
        print("  none")
        return
    for path in paths:
        print(f"  - {path}")


def unique_paths(paths: list[Path]) -> list[Path]:
    return sorted(set(paths), key=lambda path: path.as_posix())


def default_report_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_REPORT_DIR / f"pre_commit_artifacts_{timestamp}.md"


def write_report(
    report_path: Path,
    *,
    dry_run: bool,
    selected_dvc_paths: list[Path],
    deferred_dvc_paths: list[Path],
    deferred_snapshot_before: tuple[DeferredDvcFinalSnapshot, ...] | None,
    deferred_snapshot_after: tuple[DeferredDvcFinalSnapshot, ...] | None,
    rejected_unmanaged_paths: list[Path],
    git_status_before: str,
    dvc_status_before: dict[str, Any],
    dvc_status_after: dict[str, Any] | None,
    cloud_status_before: CommandResult | None,
    dvc_add_results: list[CommandResult],
    dvc_push_result: CommandResult | None,
    git_add_result: CommandResult | None,
    publication_check_result: CommandResult | None,
    reproducibility_findings: list[ReproducibilityFinding],
    staged_status: str,
    exclusive: bool = False,
) -> None:
    if not exclusive:
        report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Pre-Commit Artifact Preparation Report",
        "",
        f"Generated at UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"Dry run: `{dry_run}`",
        "",
        "## Selected DVC Targets",
        "",
    ]
    if selected_dvc_paths:
        lines.extend(f"- `{path.as_posix()}`" for path in selected_dvc_paths)
    else:
        lines.append("- none")

    lines.extend(["", "## Deferred DVC A0 Snapshot", ""])
    if deferred_snapshot_before is None and deferred_snapshot_after is None:
        lines.append("Not applicable.")
    else:
        def snapshot_records(
            records: tuple[DeferredDvcFinalSnapshot, ...] | None,
        ) -> list[dict[str, Any]] | None:
            if records is None:
                return None
            return [
                {
                    "path": record.path,
                    "device": record.device,
                    "inode": record.inode,
                    "mtime_ns": record.mtime_ns,
                    "bytes": record.size,
                    "sha256": record.sha256,
                    "mode": f"{record.mode:04o}",
                    "nlink": record.nlink,
                    "ctime_ns": record.ctime_ns,
                }
                for record in records
            ]

        snapshot_payload = {
            "before": snapshot_records(deferred_snapshot_before),
            "after": snapshot_records(deferred_snapshot_after),
            "identical": deferred_snapshot_before == deferred_snapshot_after,
        }
        lines.extend(
            [
                "```json",
                json.dumps(snapshot_payload, indent=2, sort_keys=True),
                "```",
            ]
        )

    lines.extend(["", "## Deferred DVC Targets (Not Added)", ""])
    if deferred_dvc_paths:
        lines.extend(
            f"- `OK` `{path.as_posix()}`: exact Closure V1 A0/1729 deferral; "
            "real DVC status preserved and no DVC add or push run."
            for path in deferred_dvc_paths
        )
    else:
        lines.append("- none")

    lines.extend(["", "## Rejected Unmanaged Heavy Paths", ""])
    if rejected_unmanaged_paths:
        lines.extend(f"- `{path.as_posix()}`" for path in rejected_unmanaged_paths)
    else:
        lines.append("- none")

    lines.extend(["", "## Git Status Before", "", "```text", git_status_before.rstrip() or "clean", "```"])
    lines.extend(
        [
            "",
            "## DVC Status Before",
            "",
            "```json",
            json.dumps(dvc_status_before, indent=2, sort_keys=True),
            "```",
        ]
    )
    lines.extend(["", "## DVC Status After Staging", ""])
    if dvc_status_after is None:
        lines.append("Not run.")
    else:
        lines.extend(
            [
                "```json",
                json.dumps(dvc_status_after, indent=2, sort_keys=True),
                "```",
            ]
        )

    lines.extend(["", "## DVC Cloud Status Before Push", ""])
    if cloud_status_before is None:
        lines.append("Not run.")
    else:
        lines.extend(
            [
                f"Command: `{command_text(cloud_status_before.command)}`",
                "",
                "```text",
                cloud_status_before.stdout.rstrip() or cloud_status_before.stderr.rstrip() or "(no output)",
                "```",
            ]
        )

    lines.extend(["", "## DVC Add Commands", ""])
    if dvc_add_results:
        for result in dvc_add_results:
            lines.extend(
                [
                    f"### `{command_text(result.command)}`",
                    "",
                    f"Exit code: `{result.returncode}`",
                    "",
                    "```text",
                    (result.stdout + result.stderr).rstrip() or "(no output)",
                    "```",
                    "",
                ]
            )
    else:
        lines.append("No DVC add commands were run.")

    lines.extend(["", "## DVC Push", ""])
    if dvc_push_result is None:
        lines.append("Not run.")
    else:
        lines.extend(
            [
                f"Command: `{command_text(dvc_push_result.command)}`",
                "",
                f"Exit code: `{dvc_push_result.returncode}`",
                "",
                "```text",
                (dvc_push_result.stdout + dvc_push_result.stderr).rstrip() or "(no output)",
                "```",
            ]
        )

    lines.extend(["", "## Git Add", ""])
    if git_add_result is None:
        lines.append("Not run.")
    else:
        lines.extend([f"Command: `{command_text(git_add_result.command)}`", f"Exit code: `{git_add_result.returncode}`"])

    lines.extend(["", "## Publication Check", ""])
    if publication_check_result is None:
        lines.append("Not run.")
    else:
        lines.extend(
            [
                f"Command: `{command_text(publication_check_result.command)}`",
                "",
                f"Exit code: `{publication_check_result.returncode}`",
                "",
                "```text",
                (publication_check_result.stdout + publication_check_result.stderr).rstrip() or "(no output)",
                "```",
            ]
        )

    lines.extend(["", "## Reproducibility Checks", ""])
    if reproducibility_findings:
        for finding in reproducibility_findings:
            lines.append(
                f"- `{finding.level.upper()}` `{finding.check}` `{finding.path}`: {finding.message}"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Staged Status After Preparation", "", "```text", staged_status.rstrip() or "none", "```", ""])
    report_bytes = "\n".join(lines).encode("utf-8")
    if not exclusive:
        report_path.write_bytes(report_bytes)
        return
    if report_path.is_absolute() or report_path.parent != DEFAULT_REPORT_DIR:
        raise DeferredDvcTargetError(
            "Deferred models report must be a default relative path directly under tmp"
        )
    _require_no_symlink_ancestors(report_path, anchor=Path("."))
    parent_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        parent_fd = os.open(report_path.parent, parent_flags)
    except OSError as exc:
        raise DeferredDvcTargetError("Deferred models report parent cannot be opened safely") from exc
    report_fd = -1
    try:
        opened_parent = os.fstat(parent_fd)
        lexical_parent = report_path.parent.lstat()
        if (
            not stat.S_ISDIR(opened_parent.st_mode)
            or (opened_parent.st_dev, opened_parent.st_ino)
            != (lexical_parent.st_dev, lexical_parent.st_ino)
        ):
            raise DeferredDvcTargetError("Deferred models report parent identity drifted")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            report_fd = os.open(report_path.name, flags, 0o600, dir_fd=parent_fd)
        except FileExistsError as exc:
            raise DeferredDvcTargetError(
                "Refusing to overwrite an existing deferred models report"
            ) from exc
        with os.fdopen(report_fd, "wb", closefd=False) as handle:
            handle.write(report_bytes)
            handle.flush()
            os.fsync(report_fd)
        named = os.stat(report_path.name, dir_fd=parent_fd, follow_symlinks=False)
        opened = os.fstat(report_fd)
        lexical_parent_after = report_path.parent.lstat()
        if (
            not stat.S_ISREG(opened.st_mode)
            or stat.S_IMODE(opened.st_mode) != 0o600
            or opened.st_nlink != 1
            or (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)
            or (lexical_parent_after.st_dev, lexical_parent_after.st_ino)
            != (opened_parent.st_dev, opened_parent.st_ino)
        ):
            raise DeferredDvcTargetError("Deferred models report identity drifted")
        os.fsync(parent_fd)
    finally:
        if report_fd >= 0:
            os.close(report_fd)
        os.close(parent_fd)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare Git and DVC artifacts before a manual commit.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_DVC_MANIFEST)
    parser.add_argument("--dvc-bin", default=None)
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Local report path. Defaults to a timestamped file under ignored tmp/.",
    )
    parser.add_argument("--target", action="append", default=[], help="Additional path to track with dvc add.")
    parser.add_argument(
        "--defer-dvc-target",
        action="append",
        default=[],
        help=(
            "Explicitly defer one sealed changed DVC target without dvc add. "
            "Only the exact Closure V1 A0 target 'models' is supported."
        ),
    )
    parser.add_argument("--jobs", default=None, help="DVC push jobs.")
    parser.add_argument("--yes", action="store_true", help="Accept DVC add prompts.")
    parser.add_argument("--dry-run", action="store_true", help="Print and report actions without changing Git/DVC.")
    parser.add_argument("--no-push", action="store_true", help="Run dvc add and git add, but skip dvc push.")
    parser.add_argument("--allow-unmanaged", action="store_true", help="Do not fail if unmanaged heavy paths are rejected.")
    parser.add_argument("--skip-publication-check", action="store_true")
    parser.add_argument(
        "--max-manifest-hash-bytes",
        type=int,
        default=DEFAULT_MAX_MANIFEST_HASH_BYTES,
        help="Maximum file size for recomputing experiment-manifest SHA-256 outputs.",
    )
    parser.add_argument(
        "--verify-manifest-inputs",
        action="store_true",
        help="Also recompute SHA-256 hashes for experiment-manifest inputs within the size limit.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_repo_root()
    try:
        deferred_dvc_paths = normalize_deferred_dvc_targets(
            list(args.defer_dvc_target), no_push=bool(args.no_push)
        )
        exclude_snapshot: tuple[int, int, int, str] | None = None
        if deferred_dvc_paths:
            validate_deferred_dvc_invocation(args, deferred_dvc_paths)
            exclude_snapshot = validate_deferred_dvc_git_exclude_environment()
    except DeferredDvcTargetError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    report_path = args.report or default_report_path()
    dvc_bin = resolve_dvc_bin(args.dvc_bin)
    if deferred_dvc_paths and dvc_bin != DEFAULT_DVC_BIN.as_posix():
        print("Deferred models mode requires the repository .venv/bin/dvc.", file=sys.stderr)
        return 2
    if deferred_dvc_paths:
        try:
            _require_no_symlink_ancestors(DEFAULT_DVC_BIN, anchor=Path("."))
            _require_regular_file(DEFAULT_DVC_BIN, mode=0o755)
        except DeferredDvcTargetError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    artifacts = load_configured_dvc_artifacts(args.manifest)

    git_status_before = versionable_changes()
    deferred_stage_gate = ""
    if deferred_dvc_paths:
        try:
            deferred_stage_gate = require_active_deferred_dvc_staging_gate(
                validate_deferred_dvc_pre_stage_scope(git_status_before)
            )
        except DeferredDvcTargetError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    dvc_status_before = dvc_status_json(dvc_bin)
    changed_artifacts = dvc_status_candidates(dvc_status_before, artifacts)
    missing_pointer_artifacts = declared_artifacts_missing_pointers(artifacts)
    manual_targets = unique_paths([Path(path) for path in args.target])
    unmanaged_paths = unmanaged_ignored_heavy_paths(artifacts)

    deferred_final_snapshot: tuple[DeferredDvcFinalSnapshot, ...] | None = None
    deferred_post_snapshot: tuple[DeferredDvcFinalSnapshot, ...] | None = None
    try:
        validate_deferred_dvc_target_selection(
            deferred_dvc_paths,
            artifacts=artifacts,
            changed_artifacts=changed_artifacts,
            missing_pointer_artifacts=missing_pointer_artifacts,
            manual_targets=manual_targets,
        )
        if deferred_dvc_paths:
            deferred_final_snapshot = validate_deferred_dvc_models_state(
                dvc_status_before
            )
    except DeferredDvcTargetError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if dvc_status_before and not changed_artifacts and not missing_pointer_artifacts and not manual_targets:
        print("DVC status reports changes, but no declared artifact could be matched.", file=sys.stderr)
        print("Review `dvc status` and rerun with one or more `--target PATH` options.", file=sys.stderr)
        return 1

    print("Pre-commit artifact assistant")
    print_artifact_table("DVC-tracked artifacts changed according to dvc status:", changed_artifacts)
    print_artifact_table("Declared DVC artifacts missing pointer files:", missing_pointer_artifacts)
    print_path_table("Additional manual DVC targets:", manual_targets)
    print_path_table("Deferred DVC targets (not added):", deferred_dvc_paths)
    print_path_table("Unmanaged ignored heavy paths:", unmanaged_paths)

    deferred_set = set(deferred_dvc_paths)
    changed_for_add = [
        artifact for artifact in changed_artifacts if artifact.path not in deferred_set
    ]
    selected_dvc_paths = [artifact.path for artifact in changed_for_add]
    selected_dvc_paths.extend(artifact.path for artifact in missing_pointer_artifacts)
    selected_dvc_paths.extend(manual_targets)

    rejected_unmanaged: list[Path] = []
    if unmanaged_paths:
        if args.yes:
            selected_dvc_paths.extend(unmanaged_paths)
        else:
            for path in unmanaged_paths:
                if prompt_yes_no(f"Add ignored heavy path to DVC: {path}?", default=False):
                    selected_dvc_paths.append(path)
                else:
                    rejected_unmanaged.append(path)

    selected_dvc_paths = unique_paths(selected_dvc_paths)

    if changed_for_add and not args.yes:
        if not prompt_yes_no("Run dvc add for the changed DVC-tracked artifacts?", default=True):
            print("DVC changes were detected but not accepted for dvc add.", file=sys.stderr)
            return 1

    if rejected_unmanaged and not args.allow_unmanaged:
        print("Unmanaged heavy paths were rejected. Use --allow-unmanaged only if this is intentional.", file=sys.stderr)
        return 1

    if deferred_dvc_paths and selected_dvc_paths:
        print("Deferred models mode forbids every DVC add target.", file=sys.stderr)
        return 2

    print_path_table("Selected DVC add targets:", selected_dvc_paths)

    cloud_status_before: CommandResult | None = None
    dvc_add_results: list[CommandResult] = []
    dvc_push_result: CommandResult | None = None
    git_add_result: CommandResult | None = None
    publication_check_result: CommandResult | None = None
    reproducibility_findings: list[ReproducibilityFinding] = []
    dvc_status_after: dict[str, Any] | None = None

    if args.dry_run:
        print()
        print("Dry run. No Git or DVC mutations will be made.")
        for path in selected_dvc_paths:
            print(f"would run: {command_text([dvc_bin, 'add', path.as_posix()])}")
        if not args.no_push:
            print(f"would run: {command_text([dvc_bin, 'push'])}")
        print("would run: git add -A")
    else:
        for path in selected_dvc_paths:
            if not path.exists():
                print(f"Selected DVC target does not exist: {path}", file=sys.stderr)
                return 2
            dvc_add_results.append(run_command([dvc_bin, "add", path.as_posix()], env=dvc_environment()))

        if not args.no_push:
            cloud_status_before = run_command([dvc_bin, "status", "--cloud"], check=False, env=dvc_environment())
            push_command = [dvc_bin, "push"]
            if args.jobs:
                push_command.extend(["--jobs", str(args.jobs)])
            dvc_push_result = run_command(push_command, env=dvc_environment())

    if not args.dry_run:
        publication_check_result = None
        if not args.skip_publication_check:
            publication_check_result = run_command(["scripts/check_repo_publication_ready.sh"], check=False)
            if publication_check_result.returncode != 0:
                print(publication_check_result.stdout)
                print(publication_check_result.stderr, file=sys.stderr)
                print("Publication check failed; not staging changes.", file=sys.stderr)
                return publication_check_result.returncode

        if deferred_dvc_paths:
            try:
                if validate_deferred_dvc_git_exclude_environment() != exclude_snapshot:
                    raise DeferredDvcTargetError(
                        "Deferred models Git exclude file changed before staging"
                    )
                current_status = dvc_status_json(dvc_bin)
                validate_deferred_dvc_models_state(
                    current_status,
                    expected_final_snapshot=deferred_final_snapshot,
                )
            except DeferredDvcTargetError as exc:
                print(str(exc), file=sys.stderr)
                return 2

        if deferred_dvc_paths:
            selected_scope = _deferred_dvc_staged_scopes().get(
                deferred_stage_gate
            )
            if selected_scope is None:
                print("Deferred models pre-stage gate is unknown.", file=sys.stderr)
                return 2
            git_add_command = ["git", "add", "-A", "--", *sorted(selected_scope)]
        else:
            git_add_command = ["git", "add", "-A"]
        git_add_result = run_command(git_add_command)
        staged_status = run_command(["git", "diff", "--cached", "--name-status"]).stdout
        if deferred_dvc_paths:
            try:
                if validate_deferred_dvc_staged_scope(staged_status) != deferred_stage_gate:
                    raise DeferredDvcTargetError(
                        "Deferred models H/P stage identity changed during git add"
                    )
                validate_deferred_dvc_staged_bindings(deferred_stage_gate)
                expected_scope = _deferred_dvc_staged_scopes().get(
                    deferred_stage_gate
                )
                if expected_scope is None:
                    raise DeferredDvcTargetError(
                        "Deferred models post-stage gate is unknown"
                    )
                expected_short_status = [
                    f"{status_code}  {path}"
                    for path, status_code in sorted(expected_scope.items())
                ]
                if versionable_changes().splitlines() != expected_short_status:
                    raise DeferredDvcTargetError(
                        "Deferred models short Git status differs from the exact staged scope"
                    )
                if _git_output(Path("."), "diff", "--name-status").strip():
                    raise DeferredDvcTargetError(
                        "Deferred models mode left an unstaged tracked change"
                    )
                dvc_status_after = dvc_status_json(dvc_bin)
                deferred_post_snapshot = validate_deferred_dvc_models_state(
                    dvc_status_after,
                    expected_final_snapshot=deferred_final_snapshot,
                )
                validate_deferred_dvc_staged_bindings(deferred_stage_gate)
                if validate_deferred_dvc_git_exclude_environment() != exclude_snapshot:
                    raise DeferredDvcTargetError(
                        "Deferred models Git exclude file changed during staging"
                    )
            except DeferredDvcTargetError as exc:
                print(str(exc), file=sys.stderr)
                return 2
        reproducibility_findings = reproducibility_checks(
            staged_status=staged_status,
            selected_dvc_paths=selected_dvc_paths,
            artifacts=artifacts,
            max_manifest_hash_bytes=args.max_manifest_hash_bytes,
            verify_manifest_inputs=args.verify_manifest_inputs,
        )
        if deferred_dvc_paths:
            reproducibility_findings.append(
                ReproducibilityFinding(
                    "ok",
                    "deferred_dvc",
                    DEFERRED_DVC_MODELS_TARGET.as_posix(),
                    (
                        "Exact Closure V1 A0/1729 models delta remains intentionally "
                        f"unregistered under {deferred_stage_gate}; no DVC add or push ran."
                    ),
                )
            )
            try:
                final_status = dvc_status_json(dvc_bin)
                if final_status != dvc_status_after:
                    raise DeferredDvcTargetError(
                        "Deferred models DVC status changed during reproducibility checks"
                    )
                deferred_post_snapshot = validate_deferred_dvc_models_state(
                    final_status,
                    expected_final_snapshot=deferred_final_snapshot,
                )
                validate_deferred_dvc_staged_bindings(deferred_stage_gate)
                if validate_deferred_dvc_git_exclude_environment() != exclude_snapshot:
                    raise DeferredDvcTargetError(
                        "Deferred models Git exclude file changed before reporting"
                    )
            except DeferredDvcTargetError as exc:
                print(str(exc), file=sys.stderr)
                return 2
        try:
            write_report(
                report_path,
                dry_run=args.dry_run,
                selected_dvc_paths=selected_dvc_paths,
                deferred_dvc_paths=deferred_dvc_paths,
                deferred_snapshot_before=deferred_final_snapshot,
                deferred_snapshot_after=deferred_post_snapshot,
                rejected_unmanaged_paths=rejected_unmanaged,
                git_status_before=git_status_before,
                dvc_status_before=dvc_status_before,
                dvc_status_after=dvc_status_after,
                cloud_status_before=cloud_status_before,
                dvc_add_results=dvc_add_results,
                dvc_push_result=dvc_push_result,
                git_add_result=git_add_result,
                publication_check_result=publication_check_result,
                reproducibility_findings=reproducibility_findings,
                staged_status=staged_status,
                exclusive=bool(deferred_dvc_paths),
            )
        except DeferredDvcTargetError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        if deferred_dvc_paths:
            try:
                reported_status = dvc_status_json(dvc_bin)
                if reported_status != dvc_status_after:
                    raise DeferredDvcTargetError(
                        "Deferred models DVC status changed while writing the report"
                    )
                validate_deferred_dvc_models_state(
                    reported_status,
                    expected_final_snapshot=deferred_final_snapshot,
                )
                validate_deferred_dvc_staged_bindings(deferred_stage_gate)
                if validate_deferred_dvc_git_exclude_environment() != exclude_snapshot:
                    raise DeferredDvcTargetError(
                        "Deferred models Git exclude file changed while writing the report"
                    )
            except DeferredDvcTargetError as exc:
                print(str(exc), file=sys.stderr)
                return 2
        if has_failing_findings(reproducibility_findings):
            print()
            print("Reproducibility checks failed; fix the findings and rerun the assistant.", file=sys.stderr)
            print(f"Report written: {report_path}", file=sys.stderr)
            return 1
    else:
        staged_status = "dry run"
        reproducibility_findings = [
            ReproducibilityFinding(
                "warn",
                "reproducibility",
                "-",
                "Dry run: final staged reproducibility checks were not executed.",
            )
        ]
        write_report(
            report_path,
            dry_run=args.dry_run,
            selected_dvc_paths=selected_dvc_paths,
            deferred_dvc_paths=deferred_dvc_paths,
            deferred_snapshot_before=None,
            deferred_snapshot_after=None,
            rejected_unmanaged_paths=rejected_unmanaged,
            git_status_before=git_status_before,
            dvc_status_before=dvc_status_before,
            dvc_status_after=None,
            cloud_status_before=None,
            dvc_add_results=[],
            dvc_push_result=None,
            git_add_result=None,
            publication_check_result=None,
            reproducibility_findings=reproducibility_findings,
            staged_status=staged_status,
        )

    print()
    print(f"Report written: {report_path}")
    if not args.dry_run:
        print("Changes are staged. Review with:")
        print("  git diff --cached --stat")
        print("  git diff --cached --name-status")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
