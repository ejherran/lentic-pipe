from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from src.data.prepare_commit_artifacts import validate_experiment_manifests
from src.experiments import closure_development_runtime_patch as runtime_patch
from src.experiments import lock_closure_development_runtime_patch as patch_locker
from src.experiments.closure_contract import (
    ClosureContractError,
    load_json_mapping,
    load_yaml_mapping,
    validate_json_schema,
)
from src.experiments.closure_development_runtime_patch import (
    DevelopmentRuntimePatchError,
    validate_development_runtime_patch_lock_payload,
)


DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/development_runtime_patch_lock.schema.json"
)
SHA_A = "a" * 64
SHA_B = "b" * 64
HEAD_B = "d" * 40
HEAD_C = "e" * 40
BASE_LOCK_COMMIT = "e7becdd5553decc92bbcf0af4cede7425ed12546"
BASE_LOCKED_HEAD = "4fe2d02a0abf4e044e5f2aa223c99ccc95ee7cd3"
BASE_LOCK_SHA256 = "5d858028ff5df561cc4a5e6086d9f83d08ac4c5ef6ffe27e844001f9fa495a81"
BASE_SCHEMA_SHA256 = "5314f5d15a4e516d1a0500a7ca5a69cb412ac4827f42973f26a8ec45fcd63204"

BASE_DRIFT_PATHS = [
    "src/experiments/build_closure_pipe_sequences.py",
    "src/experiments/closure_development_runtime_lock.py",
    "src/experiments/fit_closure_anfis_state.py",
    "tests/test_build_closure_pipe_sequences.py",
    "tests/test_closure_development_runtime_lock.py",
    "tests/test_fit_closure_anfis_state.py",
]
PATCH_COMPONENTS = [
    (
        "configs/closure_v1/development_runtime_patch_lock.schema.json",
        "development_runtime_patch_lock_schema",
    ),
    (
        "docs/closure_v1/E0_D_RUNTIME_PATCH_1.md",
        "development_runtime_patch_protocol",
    ),
    (
        "src/experiments/closure_development_runtime_patch.py",
        "development_runtime_patch_validator",
    ),
    (
        "src/experiments/lock_closure_development_runtime_patch.py",
        "development_runtime_patch_locker",
    ),
    (
        "tests/test_closure_development_runtime_patch.py",
        "development_runtime_patch_tests",
    ),
]
PATCH_LOCK_PATH = "reports/closure_v1/00_protocol/development_runtime_patch_lock.json"
SEED_MANIFEST_PATH = "reports/closure_v1/01_surface/anfis/seed_1729/manifest.json"
SEED_LIGHTWEIGHT_PATHS = [
    "reports/closure_v1/01_surface/anfis/seed_1729/ANFIS-N_sample_keys.csv",
    "reports/closure_v1/01_surface/anfis/seed_1729/ANFIS-F_sample_keys.csv",
    "reports/closure_v1/01_surface/anfis/seed_1729/ANFIS-T-no-current_sample_keys.csv",
    "reports/closure_v1/01_surface/anfis/seed_1729/lineage_audit.json",
    "reports/closure_v1/01_surface/anfis/seed_1729/memberships_final.csv",
    "reports/closure_v1/01_surface/anfis/seed_1729/memberships_initial.csv",
    "reports/closure_v1/01_surface/anfis/seed_1729/module_metrics.csv",
    "reports/closure_v1/01_surface/anfis/seed_1729/report.md",
    "reports/closure_v1/01_surface/anfis/seed_1729/training_curve.csv",
]
STATE_POINTER_PATH = (
    "data/closure_v1/development/anfis/seed_1729/"
    "adaptive_no_current_state.parquet.dvc"
)
ADOPTION_ARTIFACT_PATHS = [
    SEED_MANIFEST_PATH,
    *SEED_LIGHTWEIGHT_PATHS,
    STATE_POINTER_PATH,
    "models.dvc",
]

FITTED_METRIC_COLUMNS = [
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
]
UNAVAILABLE_METRIC_COLUMNS = [
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
]


def _file(
    path: str,
    role: str,
    *,
    size: int = 1,
    sha256: str = SHA_A,
    module: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": path,
        "role": role,
        "bytes": size,
        "sha256": sha256,
    }
    if module is not None:
        record["module"] = module
    return record


def _command(command: list[str]) -> dict[str, Any]:
    return {
        "command": command,
        "exit_code": 0,
        "stdout_sha256": SHA_A,
        "stderr_sha256": SHA_A,
        "passed": True,
    }


def _path_digest(paths: list[str]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _record_digest(records: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(
            json.dumps(
                record,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        digest.update(b"\n")
    return digest.hexdigest()


def _dvc_tree_bytes(records: list[dict[str, Any]]) -> bytes:
    return json.dumps(records, ensure_ascii=True, sort_keys=True).encode("utf-8")


def _frozen_seed_outputs() -> tuple[
    dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]
]:
    state = _file(
        "data/closure_v1/development/anfis/seed_1729/"
        "adaptive_no_current_state.parquet",
        "adaptive_no_current_state",
        size=1_215_081,
        sha256="c1987e31edb5b0f830f433120715f2abb7d7a375f8f38e6ad24056fc12447c69",
    )
    checkpoints = [
        _file(
            "models/closure_v1/anfis/seed_1729/ANFIS-N.pt",
            "anfis_checkpoint",
            size=5_050,
            sha256="cbf3ec20445b0cdb0b4915bb3b5fcff3a293688cdf605fb1d4300728341b61d6",
            module="ANFIS-N",
        ),
        _file(
            "models/closure_v1/anfis/seed_1729/ANFIS-F.pt",
            "anfis_checkpoint",
            size=8_250,
            sha256="741d3ab0b9980c1f4c61447b1d9150bdd24ba649ab7c7057181c7c825c7bcfc6",
            module="ANFIS-F",
        ),
        _file(
            "models/closure_v1/anfis/seed_1729/ANFIS-T-no-current.pt",
            "anfis_checkpoint",
            size=4_147,
            sha256="45064d6b3bffe102a4d4d6689f0bc0709791cd5df5b328323f96e7c3b507e6a8",
            module="ANFIS-T-no-current",
        ),
    ]
    lightweight = [
        _file(
            "reports/closure_v1/01_surface/anfis/seed_1729/ANFIS-N_sample_keys.csv",
            "sample_keys",
            size=463_207,
            sha256="754a8b8c29bdd40145f859983da64f3287ae8c527a413e0b9e8d68bb83a92b8c",
            module="ANFIS-N",
        ),
        _file(
            "reports/closure_v1/01_surface/anfis/seed_1729/ANFIS-F_sample_keys.csv",
            "sample_keys",
            size=458_422,
            sha256="f15beef010139fcb8c5ef5f729d41e3de0a67492c87982f0f8a8a0838375ac72",
            module="ANFIS-F",
        ),
        _file(
            "reports/closure_v1/01_surface/anfis/seed_1729/"
            "ANFIS-T-no-current_sample_keys.csv",
            "sample_keys",
            size=503_037,
            sha256="5b31f6b032df20b3e5a5a1d5fa2ba4b0beeeb174284ff5229b30bfe570a91114",
            module="ANFIS-T-no-current",
        ),
        _file(
            "reports/closure_v1/01_surface/anfis/seed_1729/module_metrics.csv",
            "module_metrics",
            size=1_104,
            sha256="85ae8a11f52edf9c9cf927595782a64eff74ab76f1b58f4324095bd9ef274e22",
        ),
        _file(
            "reports/closure_v1/01_surface/anfis/seed_1729/training_curve.csv",
            "training_curve",
            size=7_673,
            sha256="bace68b15b08ce460d124f113961e827d4e415863933192a2b23c632fb372af8",
        ),
        _file(
            "reports/closure_v1/01_surface/anfis/seed_1729/memberships_initial.csv",
            "memberships_initial",
            size=1_293,
            sha256="cf49de8f2aa49679baeaad9d856acc6384c76f9f31d6e4fff3436f8ec6c46467",
        ),
        _file(
            "reports/closure_v1/01_surface/anfis/seed_1729/memberships_final.csv",
            "memberships_final",
            size=1_719,
            sha256="f6d0fbcf7f04743a59a804162fb252f429e2bfe2bc4272bf27924490c7aff1bd",
        ),
        _file(
            "reports/closure_v1/01_surface/anfis/seed_1729/report.md",
            "report",
            size=444,
            sha256="feb6e21a63d73cdf1312159ab0fdde7bd46b8fa1eb8e4cf9d32c9e487822aeae",
        ),
        _file(
            "reports/closure_v1/01_surface/anfis/seed_1729/lineage_audit.json",
            "lineage_audit",
            size=2_863,
            sha256="f54c8a5cdc15de8b31dd8337fda3ac1025ef500c7ad935811a643e4216e8a894",
        ),
    ]
    return state, checkpoints, lightweight


def _payload() -> dict[str, Any]:
    state, checkpoints, lightweight = _frozen_seed_outputs()
    checkpoint_md5 = {
        "models/closure_v1/anfis/seed_1729/ANFIS-N.pt": (
            "9485f2a183c8509255ebb8b9e9606517"
        ),
        "models/closure_v1/anfis/seed_1729/ANFIS-F.pt": (
            "6a916f6077406ff7bbe7e25afd773d84"
        ),
        "models/closure_v1/anfis/seed_1729/ANFIS-T-no-current.pt": (
            "e376b6f9e3ff929da440e937e70f95f0"
        ),
    }
    tree_entries = sorted(
        [
            {"md5": f"{index:032x}", "relpath": f"legacy/model_{index:03d}.pt"}
            for index in range(173)
        ]
        + [
            {
                "md5": checkpoint_md5[record["path"]],
                "relpath": str(record["path"]).removeprefix("models/"),
            }
            for record in checkpoints
        ],
        key=lambda record: record["relpath"],
    )
    tree_cache_bytes = _dvc_tree_bytes(tree_entries)
    tree_hash_value = (
        hashlib.md5(tree_cache_bytes, usedforsecurity=False).hexdigest() + ".dir"
    )
    tree_cache_sha256 = hashlib.sha256(tree_cache_bytes).hexdigest()
    adoption_delta_records = [
        {
            "path": record["path"],
            "bytes": record["bytes"],
            "sha256": record["sha256"],
            "md5": checkpoint_md5[record["path"]],
        }
        for record in checkpoints
    ]
    seed_manifest_record = _file(
        "reports/closure_v1/01_surface/anfis/seed_1729/manifest.json",
        "seed_1729_completion_manifest",
        size=20_768,
        sha256=(
            "b38e54d21dd64edbf5a5968d9bee505569ea72b9f03c6750baf9a54114e9ef82"
        ),
    )
    bundle_records = [
        seed_manifest_record,
        *sorted([state, *checkpoints, *lightweight], key=lambda record: record["path"]),
    ]
    delta_relpaths = {
        str(record["path"]).removeprefix("models/") for record in checkpoints
    }
    base_tree_entries = [
        entry for entry in tree_entries if entry["relpath"] not in delta_relpaths
    ]
    diff_paths = sorted(
        [
            *BASE_DRIFT_PATHS,
            *(path for path, _ in PATCH_COMPONENTS),
            *ADOPTION_ARTIFACT_PATHS,
        ]
    )
    activation_paths = [
        "src/experiments/closure_development_runtime_lock.py",
        "src/experiments/fit_closure_anfis_state.py",
        "tests/test_closure_development_runtime_lock.py",
        "tests/test_fit_closure_anfis_state.py",
    ]
    adoption_paths = [path for path in diff_paths if path not in activation_paths]
    aggregate_diff = {
        "base_commit": BASE_LOCK_COMMIT,
        "patch_head": HEAD_B,
        "entries": [
            {
                "status": (
                    "M"
                    if path in {*BASE_DRIFT_PATHS, "models.dvc"}
                    else "A"
                ),
                "path": path,
            }
            for path in diff_paths
        ],
        "paths": diff_paths,
        "paths_sha256": _path_digest(diff_paths),
        "only_allowed_additions_and_modifications": True,
    }
    return {
        "lock_version": "closure_development_runtime_patch_lock_v1",
        "status": "locked",
        "gate": "E0-DLP",
        "experiment_id": "closure_v1",
        "patch_id": "development_runtime_compatibility_patch_1",
        "created_at_utc": "2026-08-04T00:00:00+00:00",
        "base_e0_dl": {
            "lock": _file(
                "reports/closure_v1/00_protocol/development_runtime_lock.json",
                "base_development_runtime_lock",
                size=95_285,
                sha256=BASE_LOCK_SHA256,
            ),
            "schema": _file(
                "configs/closure_v1/development_runtime_lock.schema.json",
                "base_development_runtime_lock_schema",
                size=20_606,
                sha256=BASE_SCHEMA_SHA256,
            ),
            "lock_commit": BASE_LOCK_COMMIT,
            "locked_repository_head": BASE_LOCKED_HEAD,
            "lock_version": "closure_development_runtime_lock_v1",
            "status": "locked",
            "git_at_h_record_count": 1,
            "git_at_h_records_sha256": SHA_A,
            "git_at_h_records": [_file("src/experiments/base.py", "base_component")],
            "base_lock_unchanged": True,
        },
        "patch_repository": {
            "head": HEAD_B,
            "branch": "main",
            "worktree_status": "clean",
            "dirty_paths": [],
            "records_verified_at_execution_head": True,
        },
        "patch_parent_publication": {
            "tracking_ref": "origin/main",
            "tracking_oid": HEAD_B,
            "remote_ref": "refs/heads/main",
            "remote_oid": HEAD_B,
            "published_head": HEAD_B,
            "execution_head": HEAD_B,
            "published_head_is_ancestor_of_execution": True,
            "local_tracking_verified": True,
            "remote_verified": True,
        },
        "publication_sequence": {
            "base_commit": BASE_LOCK_COMMIT,
            "adoption_head": HEAD_C,
            "patch_head": HEAD_B,
            "adoption_is_direct_first_parent_of_patch": True,
            "base_is_ancestor_of_adoption": True,
            "adoption_is_ancestor_of_patch": True,
            "base_to_adoption": {
                "base_commit": BASE_LOCK_COMMIT,
                "patch_head": HEAD_C,
                "entries": [
                    {
                        "status": (
                            "M"
                            if path in {
                                "src/experiments/build_closure_pipe_sequences.py",
                                "tests/test_build_closure_pipe_sequences.py",
                                "models.dvc",
                            }
                            else "A"
                        ),
                        "path": path,
                    }
                    for path in adoption_paths
                ],
                "paths": adoption_paths,
                "paths_sha256": _path_digest(adoption_paths),
                "only_allowed_additions_and_modifications": True,
            },
            "adoption_to_patch": {
                "base_commit": HEAD_C,
                "patch_head": HEAD_B,
                "entries": [
                    {"status": "M", "path": path} for path in activation_paths
                ],
                "paths": activation_paths,
                "paths_sha256": _path_digest(activation_paths),
                "only_allowed_additions_and_modifications": True,
            },
            "base_to_patch": aggregate_diff,
        },
        "base_component_drift": {
            "count": 6,
            "allowlist": BASE_DRIFT_PATHS,
            "observed_paths": BASE_DRIFT_PATHS,
            "records": [
                {
                    "path": path,
                    "base_bytes": 1,
                    "base_sha256": SHA_A,
                    "patch_bytes": 2,
                    "patch_sha256": SHA_B,
                }
                for path in BASE_DRIFT_PATHS
            ],
            "records_sha256": _record_digest(
                [
                    {
                        "path": path,
                        "base_bytes": 1,
                        "base_sha256": SHA_A,
                        "patch_bytes": 2,
                        "patch_sha256": SHA_B,
                    }
                    for path in BASE_DRIFT_PATHS
                ]
            ),
            "only_allowlisted_base_components_changed": True,
        },
        "patch_components": {
            "count": 5,
            "paths": [path for path, _ in PATCH_COMPONENTS],
            "paths_sha256": _path_digest([path for path, _ in PATCH_COMPONENTS]),
            "records": [_file(path, role) for path, role in PATCH_COMPONENTS],
            "records_sha256": _record_digest(
                [_file(path, role) for path, role in PATCH_COMPONENTS]
            ),
        },
        "patch_lock_artifact": {
            "count": 1,
            "path": PATCH_LOCK_PATH,
            "role": "external_development_runtime_patch_lock",
            "self_hash_policy": "verified_from_committed_and_published_bytes",
        },
        "git_diff": aggregate_diff,
        "compatibility_corrections": [
            {
                "issue_id": "published_ref_compatibility_patch_1",
                "producer_path": "src/experiments/closure_development_runtime_lock.py",
                "consumer_path": "src/experiments/build_closure_pipe_sequences.py",
                "field": "authorization.published_ref",
                "accepted_value": "origin/main",
                "rejected_synthetic_fixture_value": "refs/remotes/origin/main",
                "scope": "validation_compatibility_only",
                "adopted_base_seed": 1729,
                "scientific_runtime_contract_changed": False,
                "sampling_changed": False,
                "model_parameters_changed": False,
                "state_mapping_changed": False,
                "outcome_access_changed": False,
            },
            {
                "issue_id": "module_metrics_column_order_compatibility_patch_1",
                "producer_path": "src/experiments/fit_closure_anfis_state.py",
                "consumer_path": "src/experiments/build_closure_pipe_sequences.py",
                "field": "outputs.module_metrics.column_order",
                "accepted_basis": "closed_producer_csv_dialect",
                "rejected_basis": (
                    "json_object_insertion_order_after_sorted_serialization"
                ),
                "fitted_columns": FITTED_METRIC_COLUMNS,
                "unavailable_columns": UNAVAILABLE_METRIC_COLUMNS,
                "scope": "validation_compatibility_only",
                "adopted_base_seed": 1729,
                "scientific_runtime_contract_changed": False,
                "sampling_changed": False,
                "model_parameters_changed": False,
                "state_mapping_changed": False,
                "outcome_access_changed": False,
            },
            {
                "issue_id": "anfis_artifact_path_compatibility_patch_1",
                "producer_path": "src/experiments/fit_closure_anfis_state.py",
                "consumer_path": "src/experiments/build_closure_pipe_sequences.py",
                "inventory_path": "src/experiments/closure_runtime_contract.py",
                "field": "artifacts.anfis_module_path_token",
                "accepted_basis": "locked_runtime_artifact_token",
                "historical_basis": "module_display_name_interpolation",
                "future_module_tokens": {
                    "ANFIS-N": "anfis_n",
                    "ANFIS-F": "anfis_f",
                    "ANFIS-T-no-current": "anfis_t_no_current",
                },
                "historical_uppercase_paths_restricted_to_seed": 1729,
                "scope": "validation_compatibility_only",
                "adopted_base_seed": 1729,
                "scientific_runtime_contract_changed": False,
                "sampling_changed": False,
                "model_parameters_changed": False,
                "state_mapping_changed": False,
                "outcome_access_changed": False,
            },
        ],
        "adopted_seed_bundle": {
            "base_seed": 1729,
            "status": "adopted_prepatch_artifact_without_rematerialization",
            "manifest": seed_manifest_record,
            "state": state,
            "checkpoints": checkpoints,
            "lightweight_outputs": lightweight,
            "bundle_record_count": 13,
            "physical_final_count": 14,
            "completion_manifest_written_last_observed_at_adoption": True,
            "temporary_or_partial_file_count": 0,
            "bundle_records_sha256": _record_digest(bundle_records),
            "state_audit": {
                "rows": 42_110,
                "locations": 353,
                "minimum_year_month": "2000-01",
                "maximum_year_month": "2021-12",
                "role_counts": {
                    "training": 36_639,
                    "model_selection": 3_739,
                    "calibration_threshold": 1_732,
                },
                "delta_previous_month_missing_count": 8_041,
                "output_allowlist": [
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
                ],
                "zero_holdout_overlap": True,
                "zero_unknown_assignment_overlap": True,
                "no_post_2021_materialization": True,
                "future_outcomes_accessed": False,
            },
            "dvc": {
                "state_pointer": {
                    **_file(
                        STATE_POINTER_PATH,
                        "adaptive_state_dvc_pointer",
                    ),
                    "owner_strategy": "explicit_pointer",
                    "hash_name": "md5",
                    "hash_value": "183bc5e98b1d5fa5084300ded6476712",
                    "size": 1_215_081,
                    "payload_verified": True,
                },
                "models_owner": {
                    **_file("models.dvc", "anfis_models_dvc_owner"),
                    "owner_strategy": "monolithic_parent",
                    "owned_path": "models",
                    "hash_name": "md5",
                    "hash_value": tree_hash_value,
                    "size": 115_709_141,
                    "nfiles": 176,
                    "checkpoint_paths": [record["path"] for record in checkpoints],
                    "tree_bytes": len(tree_cache_bytes),
                    "tree_cache_sha256": tree_cache_sha256,
                    "tree_entry_count": 176,
                    "tree_entries_sha256": _record_digest(tree_entries),
                    "tree_entries": tree_entries,
                    "base_owner_hash_value": (
                        "458e4ebf186f91dba8608f951b998483.dir"
                    ),
                    "base_owner_size": 115_691_694,
                    "base_owner_nfiles": 173,
                    "base_tree_cache_sha256": (
                        "cf642de4acbf4b42a33415774a0603a30f5b8abe52553c073a5bf5139ebc6569"
                    ),
                    "base_tree_entries_sha256": _record_digest(base_tree_entries),
                    "adoption_delta_count": 3,
                    "adoption_delta_records": adoption_delta_records,
                    "adoption_delta_records_sha256": _record_digest(
                        adoption_delta_records
                    ),
                    "base_tree_preserved_exactly": True,
                    "adoption_delta_exactly_seed_checkpoints": True,
                    "directory_payload_verified": True,
                    "checkpoint_membership_verified": True,
                    "pointer_metadata_verified": True,
                },
                "registered": True,
            },
            "original_authorization": {
                "lock_path": (
                    "reports/closure_v1/00_protocol/development_runtime_lock.json"
                ),
                "lock_sha256": BASE_LOCK_SHA256,
                "execution_head": BASE_LOCK_COMMIT,
                "published_ref": "origin/main",
                "published_head": BASE_LOCK_COMMIT,
                "remote_main_oid": BASE_LOCK_COMMIT,
            },
            "original_manifest_mutated": False,
            "original_seed_rematerialized": False,
            "future_outcomes_accessed": False,
            "evaluation_authorized": False,
            "e0_u_authorized": False,
        },
        "environment": {
            "python_version": "3.12.0",
            "python_implementation": "CPython",
            "python_executable_name": "python",
            "platform": "Linux-test",
            "machine": "x86_64",
            "device": "cpu",
            "cublas_workspace_config": None,
            "cpu_execution_policy": {"device": "cpu"},
            "packages": [{"name": "numpy", "version": "2.0.0"}],
        },
        "dvc_remote_verification": {
            "method": "two_targeted_idempotent_pushes_v1",
            "command": [
                ".venv/bin/dvc",
                "push",
                "-j",
                "1",
                "-r",
                "gcsremote",
                STATE_POINTER_PATH,
                "models.dvc",
            ],
            "environment": {
                "LC_ALL": "C",
                "LANG": "C",
                "DVC_NO_ANALYTICS": "1",
            },
            "remote_name": "gcsremote",
            "remote_url_sha256": SHA_B,
            "targets": [
                {
                    "artifact_role": "adaptive_state",
                    "pointer_path": STATE_POINTER_PATH,
                    "pointer_sha256": SHA_A,
                    "hash_name": "md5",
                    "hash_value": "183bc5e98b1d5fa5084300ded6476712",
                    "size": 1_215_081,
                },
                {
                    "artifact_role": "anfis_models",
                    "pointer_path": "models.dvc",
                    "pointer_sha256": SHA_A,
                    "hash_name": "md5",
                    "hash_value": tree_hash_value,
                    "size": 115_709_141,
                    "nfiles": 176,
                    "tree_cache_sha256": tree_cache_sha256,
                    "tree_entries_sha256": _record_digest(tree_entries),
                },
            ],
            "attempts": [
                {
                    "attempt": attempt,
                    "exit_code": 0,
                    "stdout_sha256": SHA_A,
                    "stderr_sha256": SHA_A,
                    "normalized_result": "everything_up_to_date",
                }
                for attempt in (1, 2)
            ],
            "dvc_remote_verified_at_patch": True,
        },
        "verification": {
            "full_type_check": _command([".venv/bin/ty", "check"]),
            "focused_tests": {
                **_command(
                    [
                        ".venv/bin/pytest",
                        "tests/test_closure_development_runtime_patch.py",
                        "tests/test_build_closure_pipe_sequences.py",
                        "tests/test_closure_development_runtime_lock.py",
                        "tests/test_fit_closure_anfis_state.py",
                        "-q",
                    ]
                ),
                "environment": dict(runtime_patch.PATCH_TEST_ENVIRONMENT),
                "test_count": runtime_patch.PATCH_FOCUSED_TEST_COUNT,
            },
        },
        "audits": {
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
            "three_runtime_compatibility_corrections_verified": True,
            "patch_records_verified_at_execution_head": True,
            "patch_lock_artifact_verified": True,
            "seed_1729_bundle_verified": True,
            "seed_1729_preserved_without_rematerialization": True,
            "dvc_ownership_verified": True,
            "dvc_remote_verified_at_patch": True,
            "zero_holdout_overlap": True,
            "zero_unknown_assignment_overlap": True,
            "no_post_2021_materialization": True,
            "environment_locked": True,
            "legacy_summary_shape_verified": True,
        },
        "authorizations": {
            "development_fit_authorized": True,
            "evaluation_authorized": False,
            "e0_u_authorized": False,
        },
        "seals": {
            "future_outcomes_accessed": False,
            "post_2021_outcome_semantic_decode": False,
            "lock_generation_reads_scientific_outcome_rows": False,
            "lock_generation_reads_post_2021_outcomes": False,
            "scientific_runtime_contract_changed": False,
            "base_e0_dl_replaced": False,
            "original_seed_manifest_mutated": False,
            "original_seed_rematerialized": False,
            "does_not_replace_e0_m_model_lock": True,
        },
    }


@pytest.fixture
def schema() -> dict[str, Any]:
    return load_json_mapping(DEFAULT_PATCH_LOCK_SCHEMA)


@pytest.fixture
def payload() -> dict[str, Any]:
    return _payload()


def test_patch_schema_has_no_duplicate_json_object_keys() -> None:
    def closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AssertionError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    json.loads(
        DEFAULT_PATCH_LOCK_SCHEMA.read_text(encoding="utf-8"),
        object_pairs_hook=closed_object,
    )


def _assert_rejected(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    with pytest.raises(ClosureContractError):
        validate_json_schema(
            payload,
            schema,
            instance_path="$.development_runtime_patch_lock",
        )


def test_patch_lock_schema_accepts_closed_structural_fixture(
    payload: dict[str, Any], schema: dict[str, Any]
) -> None:
    validate_json_schema(
        payload,
        schema,
        instance_path="$.development_runtime_patch_lock",
    )


def test_patch_lock_semantic_validator_accepts_closed_fixture(
    payload: dict[str, Any],
    schema: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runtime_patch,
        "_validate_base_models_tree_identity",
        lambda _entries: None,
    )
    validate_development_runtime_patch_lock_payload(payload, schema)


@pytest.mark.parametrize("index", range(6))
def test_patch_lock_schema_closes_each_base_drift_path(
    index: int, payload: dict[str, Any], schema: dict[str, Any]
) -> None:
    mutated = copy.deepcopy(payload)
    mutated["base_component_drift"]["records"][index]["path"] = "src/other.py"
    _assert_rejected(mutated, schema)


def test_patch_lock_schema_requires_exact_six_base_drift_records(
    payload: dict[str, Any], schema: dict[str, Any]
) -> None:
    mutated = copy.deepcopy(payload)
    mutated["base_component_drift"]["records"].pop()
    _assert_rejected(mutated, schema)


@pytest.mark.parametrize("index", range(5))
def test_patch_lock_schema_closes_each_h_dlp_component(
    index: int, payload: dict[str, Any], schema: dict[str, Any]
) -> None:
    mutated = copy.deepcopy(payload)
    mutated["patch_components"]["records"][index]["path"] = "src/other.py"
    _assert_rejected(mutated, schema)


def test_patch_lock_schema_requires_document_as_fifth_component_class(
    payload: dict[str, Any], schema: dict[str, Any]
) -> None:
    assert "docs/closure_v1/E0_D_RUNTIME_PATCH_1.md" in payload[
        "patch_components"
    ]["paths"]
    mutated = copy.deepcopy(payload)
    mutated["patch_components"]["paths"].remove(
        "docs/closure_v1/E0_D_RUNTIME_PATCH_1.md"
    )
    _assert_rejected(mutated, schema)


def test_patch_lock_schema_closes_single_external_lock_path(
    payload: dict[str, Any], schema: dict[str, Any]
) -> None:
    mutated = copy.deepcopy(payload)
    mutated["patch_lock_artifact"]["path"] = (
        "reports/closure_v1/00_protocol/other.json"
    )
    _assert_rejected(mutated, schema)


@pytest.mark.parametrize("index", range(3))
def test_patch_lock_schema_requires_all_three_compatibility_corrections(
    index: int, payload: dict[str, Any], schema: dict[str, Any]
) -> None:
    mutated = copy.deepcopy(payload)
    mutated["compatibility_corrections"].pop(index)
    _assert_rejected(mutated, schema)


def test_patch_lock_schema_rejects_synthetic_publication_ref(
    payload: dict[str, Any], schema: dict[str, Any]
) -> None:
    mutated = copy.deepcopy(payload)
    mutated["compatibility_corrections"][0]["accepted_value"] = (
        "refs/remotes/origin/main"
    )
    _assert_rejected(mutated, schema)


def test_patch_lock_schema_rejects_json_key_order_as_metrics_dialect(
    payload: dict[str, Any], schema: dict[str, Any]
) -> None:
    mutated = copy.deepcopy(payload)
    mutated["compatibility_corrections"][1]["fitted_columns"] = sorted(
        FITTED_METRIC_COLUMNS
    )
    _assert_rejected(mutated, schema)


def test_patch_lock_schema_rejects_display_names_as_future_artifact_tokens(
    payload: dict[str, Any], schema: dict[str, Any]
) -> None:
    mutated = copy.deepcopy(payload)
    mutated["compatibility_corrections"][2]["future_module_tokens"]["ANFIS-N"] = (
        "ANFIS-N"
    )
    _assert_rejected(mutated, schema)


@pytest.mark.parametrize(
    ("record_name", "foreign_key", "foreign_value"),
    [
        ("state_pointer", "nfiles", 176),
        ("models_owner", "payload_verified", True),
    ],
)
def test_patch_lock_schema_separates_state_and_models_dvc_records(
    record_name: str,
    foreign_key: str,
    foreign_value: Any,
    payload: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    mutated = copy.deepcopy(payload)
    mutated["adopted_seed_bundle"]["dvc"][record_name][foreign_key] = foreign_value
    _assert_rejected(mutated, schema)


@pytest.mark.parametrize(
    "mutation",
    [
        "tree_digest",
        "tree_hash",
        "tree_bytes",
        "tree_cache_digest",
        "base_digest",
        "base_owner_hash",
        "base_cache_digest",
        "checkpoint_md5",
        "delta_digest",
        "state_pointer",
        "state_roles",
        "dvc_target",
        "publication_diff",
    ],
)
def test_patch_lock_semantics_reject_derived_dvc_or_state_drift(
    mutation: str,
    payload: dict[str, Any],
    schema: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runtime_patch,
        "_validate_base_models_tree_identity",
        lambda _entries: None,
    )
    mutated = copy.deepcopy(payload)
    bundle = mutated["adopted_seed_bundle"]
    owner = bundle["dvc"]["models_owner"]
    if mutation == "tree_digest":
        owner["tree_entries_sha256"] = SHA_B
    elif mutation == "tree_hash":
        owner["hash_value"] = "0" * 32 + ".dir"
    elif mutation == "tree_bytes":
        owner["tree_bytes"] += 1
    elif mutation == "tree_cache_digest":
        owner["tree_cache_sha256"] = SHA_B
    elif mutation == "base_digest":
        owner["base_tree_entries_sha256"] = SHA_B
    elif mutation == "base_owner_hash":
        owner["base_owner_hash_value"] = "0" * 32 + ".dir"
    elif mutation == "base_cache_digest":
        owner["base_tree_cache_sha256"] = SHA_B
    elif mutation == "checkpoint_md5":
        checkpoint_entry = next(
            entry
            for entry in owner["tree_entries"]
            if entry["relpath"] == "closure_v1/anfis/seed_1729/ANFIS-N.pt"
        )
        checkpoint_entry["md5"] = "1" * 32
        owner["tree_entries_sha256"] = _record_digest(owner["tree_entries"])
    elif mutation == "delta_digest":
        owner["adoption_delta_records_sha256"] = SHA_B
    elif mutation == "state_pointer":
        bundle["dvc"]["state_pointer"]["size"] += 1
    elif mutation == "state_roles":
        bundle["state_audit"]["role_counts"]["model_selection"] -= 1
        bundle["state_audit"]["role_counts"]["calibration_threshold"] += 1
    elif mutation == "dvc_target":
        mutated["dvc_remote_verification"]["targets"][1]["tree_entries_sha256"] = (
            SHA_B
        )
    elif mutation == "publication_diff":
        mutated["publication_sequence"]["base_to_adoption"]["entries"][0][
            "status"
        ] = "M"
    else:  # pragma: no cover - parametrization is closed above
        raise AssertionError(mutation)
    with pytest.raises(DevelopmentRuntimePatchError):
        validate_development_runtime_patch_lock_payload(mutated, schema)


@pytest.mark.parametrize(
    ("collection", "index"),
    [("state", None), *[("checkpoints", index) for index in range(3)], *[("lightweight_outputs", index) for index in range(9)]],
)
def test_patch_lock_schema_freezes_all_thirteen_seed_outputs(
    collection: str,
    index: int | None,
    payload: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    mutated = copy.deepcopy(payload)
    bundle = mutated["adopted_seed_bundle"]
    record = bundle[collection] if index is None else bundle[collection][index]
    record["sha256"] = SHA_B
    _assert_rejected(mutated, schema)


def test_patch_lock_schema_freezes_seed_completion_manifest(
    payload: dict[str, Any], schema: dict[str, Any]
) -> None:
    mutated = copy.deepcopy(payload)
    mutated["adopted_seed_bundle"]["manifest"]["bytes"] += 1
    _assert_rejected(mutated, schema)


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("patch_parent_publication", "published_head_is_ancestor_of_execution", False),
        ("patch_repository", "records_verified_at_execution_head", False),
        ("audits", "patch_records_verified_at_execution_head", False),
    ],
)
def test_patch_lock_schema_requires_publication_ancestry_and_execution_records(
    section: str,
    field: str,
    value: bool,
    payload: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    mutated = copy.deepcopy(payload)
    mutated[section][field] = value
    _assert_rejected(mutated, schema)


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("authorizations", "development_fit_authorized", False),
        ("authorizations", "evaluation_authorized", True),
        ("authorizations", "e0_u_authorized", True),
        ("seals", "future_outcomes_accessed", True),
        ("seals", "lock_generation_reads_scientific_outcome_rows", True),
        ("seals", "lock_generation_reads_post_2021_outcomes", True),
        ("seals", "original_seed_manifest_mutated", True),
        ("seals", "original_seed_rematerialized", True),
        ("seals", "does_not_replace_e0_m_model_lock", False),
    ],
)
def test_patch_lock_schema_fails_closed_on_authorization_or_seal_drift(
    section: str,
    field: str,
    value: bool,
    payload: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    mutated = copy.deepcopy(payload)
    mutated[section][field] = value
    _assert_rejected(mutated, schema)


def test_patch_lock_schema_rejects_unknown_root_fields(
    payload: dict[str, Any], schema: dict[str, Any]
) -> None:
    mutated = copy.deepcopy(payload)
    mutated["unexpected"] = True
    _assert_rejected(mutated, schema)


def test_planned_model_owner_paths_use_locked_tokens_and_freeze_seed_1729_anfis() -> None:
    runtime = load_yaml_mapping(Path("configs/closure_v1/development_runtime.yaml"))
    paths = runtime_patch._planned_model_relpaths(runtime)

    assert "closure_v1/anfis/seed_1729/anfis_n.pt" not in paths
    assert "closure_v1/anfis/seed_1729/ANFIS-N.pt" not in paths
    assert "closure_v1/pipe/P0/seed_1729.pt" in paths
    assert "closure_v1/anfis/seed_20260612/anfis_n.pt" in paths
    assert not any("ANFIS-" in path for path in paths)


def test_publication_path_cardinalities_are_closed() -> None:
    assert len(runtime_patch.PATCH_ADOPTION_DIFF_ALLOWLIST) == 19
    assert len(runtime_patch.PATCH_ACTIVATION_PATHS) == 4
    assert len(runtime_patch.PATCH_PARENT_DIFF_ALLOWLIST) == 23
    assert set(runtime_patch.PATCH_ACTIVATION_PATHS).isdisjoint(
        runtime_patch.PATCH_ADOPTION_DIFF_ALLOWLIST
    )


def test_current_models_owner_allows_only_published_planned_additions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pointer = tmp_path / "models.dvc"
    pointer.write_bytes(b"current pointer\n")
    locked = {
        "sha256": "1" * 64,
        "tree_entries": [{"md5": "a" * 32, "relpath": "legacy/model.pt"}],
    }
    current = {
        "sha256": "2" * 64,
        "tree_entries": [
            {"md5": "a" * 32, "relpath": "legacy/model.pt"},
            {"md5": "b" * 32, "relpath": "closure_v1/pipe/P0/seed_1729.pt"},
        ],
    }
    monkeypatch.setattr(runtime_patch, "_read_models_owner_record", lambda: current)
    monkeypatch.setattr(runtime_patch, "_validate_record_at_head", lambda *_a, **_k: None)
    monkeypatch.setattr(
        runtime_patch,
        "_planned_model_relpaths",
        lambda _runtime: {"closure_v1/pipe/P0/seed_1729.pt"},
    )
    monkeypatch.setattr(runtime_patch, "_resolve", lambda _path: pointer)
    monkeypatch.setattr(runtime_patch, "_require_ancestor", lambda *_a: None)
    monkeypatch.setattr(runtime_patch, "_git", lambda *_a, **_k: HEAD_B)
    monkeypatch.setattr(
        runtime_patch,
        "_git_blob",
        lambda _head, _path: pointer.read_bytes(),
    )

    runtime_patch._validate_current_models_owner(
        locked,
        execution_head=HEAD_B,
        runtime={},
    )

    current["tree_entries"][1]["relpath"] = "closure_v1/unplanned.pt"
    with pytest.raises(DevelopmentRuntimePatchError, match="unplanned"):
        runtime_patch._validate_current_models_owner(
            locked,
            execution_head=HEAD_B,
            runtime={},
        )


def test_locked_models_owner_reconstructs_without_historical_dvc_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, checkpoints, _ = _frozen_seed_outputs()
    base_entries = [{"md5": "0" * 32, "relpath": "legacy/model.pt"}]
    checkpoint_entries = [
        {
            "md5": runtime_patch.SEED_CHECKPOINT_MD5[str(record["path"])],
            "relpath": str(record["path"]).removeprefix("models/"),
        }
        for record in checkpoints
    ]
    entries = sorted([*base_entries, *checkpoint_entries], key=lambda item: item["relpath"])
    base_tree = runtime_patch._dvc_tree_bytes(base_entries)
    full_tree = runtime_patch._dvc_tree_bytes(entries)
    base_md5 = hashlib.md5(base_tree, usedforsecurity=False).hexdigest() + ".dir"
    full_md5 = hashlib.md5(full_tree, usedforsecurity=False).hexdigest() + ".dir"
    delta_records = [
        {
            "path": record["path"],
            "bytes": record["bytes"],
            "sha256": record["sha256"],
            "md5": runtime_patch.SEED_CHECKPOINT_MD5[str(record["path"])],
        }
        for record in checkpoints
    ]
    owner = {
        "path": "models.dvc",
        "role": "anfis_models_dvc_owner",
        "bytes": 1,
        "sha256": SHA_A,
        "owner_strategy": "monolithic_parent",
        "owned_path": "models",
        "hash_name": "md5",
        "hash_value": full_md5,
        "size": 100,
        "nfiles": 4,
        "checkpoint_paths": [record["path"] for record in checkpoints],
        "tree_bytes": len(full_tree),
        "tree_cache_sha256": hashlib.sha256(full_tree).hexdigest(),
        "tree_entry_count": 4,
        "tree_entries_sha256": _record_digest(entries),
        "tree_entries": entries,
        "base_owner_hash_value": base_md5,
        "base_owner_size": 50,
        "base_owner_nfiles": 1,
        "base_tree_cache_sha256": hashlib.sha256(base_tree).hexdigest(),
        "base_tree_entries_sha256": _record_digest(base_entries),
        "adoption_delta_count": 3,
        "adoption_delta_records": delta_records,
        "adoption_delta_records_sha256": _record_digest(delta_records),
        "base_tree_preserved_exactly": True,
        "adoption_delta_exactly_seed_checkpoints": True,
        "directory_payload_verified": True,
        "checkpoint_membership_verified": True,
        "pointer_metadata_verified": True,
    }
    pointer = (
        "outs:\n"
        f"- md5: {full_md5}\n"
        "  size: 100\n"
        "  nfiles: 4\n"
        "  hash: md5\n"
        "  path: models\n"
    ).encode("utf-8")
    constants = {
        "EXPECTED_BASE_MODELS_OWNER_MD5": base_md5,
        "EXPECTED_BASE_MODELS_OWNER_SIZE": 50,
        "EXPECTED_BASE_MODELS_OWNER_NFILES": 1,
        "EXPECTED_BASE_MODELS_TREE_BYTES": len(base_tree),
        "EXPECTED_BASE_MODELS_TREE_SHA256": hashlib.sha256(base_tree).hexdigest(),
        "EXPECTED_ADOPTED_MODELS_OWNER_SIZE": 100,
        "EXPECTED_ADOPTED_MODELS_OWNER_NFILES": 4,
    }
    for name, value in constants.items():
        monkeypatch.setattr(runtime_patch, name, value)
    monkeypatch.setattr(runtime_patch, "_validate_record_at_head", lambda *_a, **_k: None)
    monkeypatch.setattr(runtime_patch, "_git_blob", lambda _head, _path: pointer)
    monkeypatch.setattr(
        runtime_patch,
        "_load_models_tree_entries",
        lambda _md5: (_ for _ in ()).throw(AssertionError("historical cache read")),
    )

    runtime_patch._validate_locked_models_owner(owner, patch_head=HEAD_B)


def test_models_owner_rejects_symlinked_physical_payloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    models_root = tmp_path / "models"
    models_root.mkdir()
    outside = tmp_path / "outside.pt"
    outside.write_bytes(b"outside")
    (models_root / "escape.pt").symlink_to(outside)
    pointer = tmp_path / "models.dvc"
    pointer.write_text(
        "outs:\n"
        "- md5: 00000000000000000000000000000000.dir\n"
        "  size: 7\n"
        "  nfiles: 1\n"
        "  hash: md5\n"
        "  path: models\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        runtime_patch,
        "_file_record",
        lambda *_a, **_k: {
            "path": "models.dvc",
            "role": "anfis_models_dvc_owner",
            "bytes": pointer.stat().st_size,
            "sha256": hashlib.sha256(pointer.read_bytes()).hexdigest(),
        },
    )
    monkeypatch.setattr(
        runtime_patch,
        "_resolve",
        lambda path: models_root if str(path) == "models" else pointer,
    )

    with pytest.raises(DevelopmentRuntimePatchError, match="symbolic links"):
        runtime_patch._read_models_owner_record()


def test_exact_frozen_seed_context_requires_published_patch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = load_json_mapping(Path(SEED_MANIFEST_PATH))
    expected_bytes, expected_sha256 = runtime_patch.EXPECTED_SEED_FINALS[
        SEED_MANIFEST_PATH
    ]
    calls: list[dict[str, Any]] = []

    def fake_loader(**kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        calls.append(kwargs)
        return (
            {
                "adopted_seed_bundle": {
                    "base_seed": 1729,
                    "manifest": {
                        "path": SEED_MANIFEST_PATH,
                        "role": "seed_1729_completion_manifest",
                        "bytes": expected_bytes,
                        "sha256": expected_sha256,
                    },
                    "original_manifest_mutated": False,
                    "original_seed_rematerialized": False,
                }
            },
            {},
        )

    monkeypatch.setattr(
        runtime_patch,
        "load_and_validate_development_runtime_patch_lock",
        fake_loader,
    )
    monkeypatch.setattr(runtime_patch, "_validate_record_at_head", lambda *_a, **_k: None)

    context = runtime_patch.require_adopted_seed_1729_consumer_context(manifest)

    assert context is not None
    assert context["historical_uppercase_artifact_paths"] is True
    assert calls == [{"require_published": True, "require_physical_artifacts": True}]


def test_locker_companion_is_non_authoritative_and_closes_four_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        patch_locker,
        "_file_record",
        lambda path, *, role, expected_owner=None: {
            "path": path.as_posix(),
            "role": role,
            "bytes": 1,
            "sha256": SHA_A,
        },
    )
    monkeypatch.setattr(patch_locker, "_is_owned", lambda _owner: True)

    companion = patch_locker._companion_manifest(
        output=runtime_patch.DEFAULT_PATCH_LOCK_PATH,
        output_owner=patch_locker._OwnedPath(Path(PATCH_LOCK_PATH), 1, 1),
        created_at_utc="2026-08-04T00:00:00+00:00",
    )

    assert companion["status"] == "completed"
    assert companion["authoritative_contract"] is False
    assert companion["authoritative_lock_path"] == PATCH_LOCK_PATH
    assert [record["path"] for record in companion["inputs"]] == [
        "reports/closure_v1/00_protocol/development_runtime_lock.json",
        "configs/closure_v1/development_runtime_lock.schema.json",
        "configs/closure_v1/development_runtime_patch_lock.schema.json",
        "src/experiments/closure_development_runtime_patch.py",
    ]


@pytest.mark.parametrize("candidate_index", range(4))
@pytest.mark.parametrize("entry_type", ["regular", "broken_internal", "broken_external"])
def test_locker_refuses_every_final_or_guard_even_when_symlink_is_broken(
    candidate_index: int,
    entry_type: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = tmp_path / "lock.json"
    manifest = tmp_path / "manifest.json"
    candidates = (
        lock,
        patch_locker._temporary_path(lock),
        manifest,
        patch_locker._temporary_path(manifest),
    )
    target = candidates[candidate_index]
    if entry_type == "regular":
        target.write_text("occupied\n", encoding="utf-8")
    else:
        missing = (
            tmp_path / "missing"
            if entry_type == "broken_internal"
            else tmp_path.parent / f"{tmp_path.name}-external-missing"
        )
        assert not missing.exists()
        target.symlink_to(missing)

    def closed(_path: Path, expected: Path) -> Path:
        return lock if expected == patch_locker.DEFAULT_PATCH_LOCK_PATH else manifest

    (tmp_path / "tmp").mkdir()
    monkeypatch.setattr(patch_locker, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        patch_locker,
        "OUTPUT_GUARD_DIRECTORY",
        tmp_path / "tmp" / "closure_v1_e0_dlp_locker",
    )
    monkeypatch.setattr(patch_locker, "_closed_output_path", closed)

    with pytest.raises(DevelopmentRuntimePatchError, match="Refusing to overwrite"):
        patch_locker._refuse_existing_outputs(Path("lock"), Path("manifest"))


def test_output_guard_is_exclusive_and_removes_only_its_inode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(patch_locker, "PROJECT_ROOT", tmp_path)
    path = tmp_path / "lock.json.tmp"
    guard = patch_locker._open_output_guard(path)
    try:
        with pytest.raises(DevelopmentRuntimePatchError, match="existing"):
            patch_locker._open_output_guard(path)
    finally:
        patch_locker._release_output_guard(guard)
    assert not os.path.lexists(path)


def test_output_guards_do_not_change_real_git_status() -> None:
    before = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=patch_locker.PROJECT_ROOT,
        check=True,
        capture_output=True,
    ).stdout
    guards = patch_locker._acquire_output_guards(
        patch_locker.DEFAULT_PATCH_LOCK_PATH,
        patch_locker.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
    )
    try:
        after = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=patch_locker.PROJECT_ROOT,
            check=True,
            capture_output=True,
        ).stdout
        assert before == after
        assert all(
            guard.owned.path.is_relative_to(patch_locker.PROJECT_ROOT / "tmp")
            for guard in guards
        )
    finally:
        for guard in reversed(guards):
            patch_locker._release_output_guard(guard)


def test_output_guard_directory_is_created_in_a_fresh_clone_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    output = reports / "lock.json"
    manifest = reports / "manifest.json"
    guard_directory = tmp_path / "tmp" / "closure_v1_e0_dlp_locker"
    monkeypatch.setattr(patch_locker, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(patch_locker, "OUTPUT_GUARD_DIRECTORY", guard_directory)
    monkeypatch.setattr(
        patch_locker,
        "_closed_output_path",
        lambda _path, expected: (
            output if expected == patch_locker.DEFAULT_PATCH_LOCK_PATH else manifest
        ),
    )

    paths = patch_locker._output_guard_paths(
        Path("lock"),
        Path("manifest"),
        create_directory=True,
    )

    assert guard_directory.is_dir()
    assert paths == tuple(
        guard_directory / name for name in patch_locker.OUTPUT_GUARD_NAMES
    )


def test_fixed_verification_executable_rejects_a_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bin_directory = tmp_path / ".venv" / "bin"
    bin_directory.mkdir(parents=True)
    target = tmp_path / "tool"
    target.write_text("#!/bin/sh\n", encoding="utf-8")
    target.chmod(0o700)
    (bin_directory / "pytest").symlink_to(target)
    monkeypatch.setattr(patch_locker, "PROJECT_ROOT", tmp_path)

    with pytest.raises(DevelopmentRuntimePatchError, match="not a regular executable"):
        patch_locker._require_fixed_verification_executable(
            (".venv/bin/pytest", "tests/test_example.py")
        )


def test_guarded_publication_never_clobbers_a_racing_final(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(patch_locker, "PROJECT_ROOT", tmp_path)
    output = tmp_path / "lock.json"
    guard = patch_locker._open_output_guard(tmp_path / "lock.json.tmp")
    output.write_bytes(b"external\n")
    monkeypatch.setattr(
        patch_locker,
        "_closed_output_path",
        lambda _path, _expected: output,
    )
    monkeypatch.setattr(
        patch_locker,
        "_relative",
        lambda _path: patch_locker.DEFAULT_PATCH_LOCK_PATH.as_posix(),
    )
    try:
        with pytest.raises(DevelopmentRuntimePatchError, match="Refusing to overwrite"):
            patch_locker._publish_guarded_json({"lock": True}, Path("lock"), guard)
    finally:
        patch_locker._release_output_guard(guard)
    assert output.read_bytes() == b"external\n"


def test_guarded_publication_anchors_the_output_parent_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guard_directory = tmp_path / "guards"
    output_parent = tmp_path / "reports"
    moved_parent = tmp_path / "reports-moved"
    external_parent = tmp_path / "external"
    guard_directory.mkdir()
    output_parent.mkdir()
    external_parent.mkdir()
    output = output_parent / "lock.json"
    guard = patch_locker._open_output_guard(guard_directory / "lock.guard")
    monkeypatch.setattr(patch_locker, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        patch_locker,
        "_closed_output_path",
        lambda _path, _expected: output,
    )
    monkeypatch.setattr(
        patch_locker,
        "_relative",
        lambda _path: patch_locker.DEFAULT_PATCH_LOCK_PATH.as_posix(),
    )
    real_link = os.link

    def racing_link(src: str, dst: str, **kwargs: Any) -> None:
        output_parent.rename(moved_parent)
        output_parent.symlink_to(external_parent, target_is_directory=True)
        real_link(src, dst, **kwargs)

    monkeypatch.setattr(patch_locker.os, "link", racing_link)
    try:
        with pytest.raises(DevelopmentRuntimePatchError, match="parent changed"):
            patch_locker._publish_guarded_json({"lock": True}, Path("lock"), guard)
    finally:
        patch_locker._release_output_guard(guard)

    assert not (moved_parent / "lock.json").exists()
    assert not (external_parent / "lock.json").exists()


def test_owned_rollback_preserves_a_replacement_inode(tmp_path: Path) -> None:
    output = tmp_path / "lock.json"
    output.write_bytes(b"owned\n")
    owned = patch_locker._owned_path(output, context="test output")
    output.unlink()
    output.write_bytes(b"replacement\n")

    patch_locker._unlink_if_owned(owned)

    assert output.read_bytes() == b"replacement\n"


def test_second_publication_failure_rolls_back_only_owned_inodes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = tmp_path / "lock.json"
    manifest = tmp_path / "manifest.json"
    prelock = {"runtime": {}, "adopted_seed_bundle": {}}
    snapshots = iter((prelock, prelock))
    monkeypatch.setattr(patch_locker, "_require_default_outputs", lambda *_a: None)
    monkeypatch.setattr(patch_locker, "_require_default_inputs", lambda **_k: None)
    monkeypatch.setattr(patch_locker, "_acquire_output_guards", lambda *_a: (object(), object()))
    monkeypatch.setattr(patch_locker, "_release_output_guard", lambda _guard: None)
    monkeypatch.setattr(
        patch_locker,
        "collect_patch_prelock_state",
        lambda **_k: next(snapshots),
    )
    monkeypatch.setattr(patch_locker, "command_evidence", lambda _command: {})
    monkeypatch.setattr(patch_locker, "_focused_test_evidence", lambda _command: {})
    monkeypatch.setattr(
        patch_locker,
        "verify_patch_dvc_remote_by_idempotent_push",
        lambda *_a: {},
    )
    monkeypatch.setattr(
        patch_locker,
        "build_development_runtime_patch_lock_payload",
        lambda *_a, **_k: {},
    )
    monkeypatch.setattr(patch_locker, "load_json_mapping", lambda _path: {})
    monkeypatch.setattr(
        patch_locker,
        "validate_development_runtime_patch_lock_payload",
        lambda *_a: None,
    )
    monkeypatch.setattr(patch_locker, "_companion_manifest", lambda **_k: {})
    calls = 0

    def publish(_payload: Any, path: Path, _guard: object) -> patch_locker._OwnedPath:
        nonlocal calls
        calls += 1
        if calls == 1:
            path.write_bytes(b"owned\n")
            return patch_locker._owned_path(path, context="test lock")
        lock.unlink()
        lock.write_bytes(b"replacement\n")
        raise RuntimeError("second publication failed")

    monkeypatch.setattr(patch_locker, "_publish_guarded_json", publish)

    with pytest.raises(RuntimeError, match="second publication failed"):
        patch_locker.create_development_runtime_patch_lock(
            base_lock_path=patch_locker.DEFAULT_LOCK_PATH,
            base_lock_schema=patch_locker.DEFAULT_LOCK_SCHEMA,
            runtime_config=patch_locker.DEFAULT_RUNTIME_CONFIG,
            runtime_schema=patch_locker.DEFAULT_RUNTIME_SCHEMA,
            patch_lock_schema=patch_locker.DEFAULT_PATCH_LOCK_SCHEMA,
            output=lock,
            manifest_output=manifest,
            device="cpu",
            verify_dvc_remote_by_idempotent_push_flag=True,
        )

    assert lock.read_bytes() == b"replacement\n"
    assert not manifest.exists()


@pytest.mark.parametrize("target_scope", ["internal", "external"])
def test_publication_reader_rejects_companion_symlinks(
    target_scope: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = (
        tmp_path / "target.json"
        if target_scope == "internal"
        else tmp_path.parent / f"{tmp_path.name}-target.json"
    )
    target.write_bytes(b"{}\n")
    link = tmp_path / "manifest.json"
    link.symlink_to(target)
    monkeypatch.setattr(runtime_patch, "_lexical_repository_path", lambda _path: link)
    monkeypatch.setattr(runtime_patch, "_relative", lambda _path: "manifest.json")

    with pytest.raises(DevelopmentRuntimePatchError, match="not a regular file"):
        runtime_patch._read_regular_repository_bytes(link, context="test companion")


def test_regular_json_loader_rejects_duplicate_lock_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = tmp_path / "lock.json"
    lock.write_bytes(b'{"status":"locked","status":"replaced"}\n')
    monkeypatch.setattr(runtime_patch, "_lexical_repository_path", lambda _path: lock)
    monkeypatch.setattr(runtime_patch, "_relative", lambda _path: "lock.json")

    with pytest.raises(DevelopmentRuntimePatchError, match="duplicate JSON key"):
        runtime_patch._load_regular_json_mapping(lock, context="test lock")


def test_companion_decoder_rejects_duplicate_keys() -> None:
    with pytest.raises(DevelopmentRuntimePatchError, match="duplicate JSON key"):
        runtime_patch._decode_json_mapping_bytes(
            b'{"status":"bad","status":"completed"}\n',
            context="E0-DLP companion",
        )


def test_focused_evidence_sanitizes_pytest_environment_and_rejects_collect_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, str] = {}
    monkeypatch.setenv("PYTEST_ADDOPTS", "--collect-only")
    monkeypatch.setenv("PYTEST_PLUGINS", "untrusted_plugin")

    def fake_run(*_args: Any, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        observed.update(kwargs["env"])
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=b"193 tests collected in 0.10s\n",
            stderr=b"",
        )

    monkeypatch.setattr(patch_locker.subprocess, "run", fake_run)

    with pytest.raises(DevelopmentRuntimePatchError, match="exact no-skip test count"):
        patch_locker._focused_test_evidence(runtime_patch.PATCH_FOCUSED_TEST_COMMAND)

    assert {key: observed[key] for key in runtime_patch.PATCH_TEST_ENVIRONMENT} == dict(
        runtime_patch.PATCH_TEST_ENVIRONMENT
    )


def test_focused_evidence_requires_and_records_the_exact_pass_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summary = f"{runtime_patch.PATCH_FOCUSED_TEST_COUNT} passed in 0.10s\n".encode()
    monkeypatch.setattr(
        patch_locker.subprocess,
        "run",
        lambda *_a, **_k: subprocess.CompletedProcess(
            args=[], returncode=0, stdout=summary, stderr=b""
        ),
    )

    evidence = patch_locker._focused_test_evidence(
        runtime_patch.PATCH_FOCUSED_TEST_COMMAND
    )

    assert evidence["test_count"] == runtime_patch.PATCH_FOCUSED_TEST_COUNT
    assert evidence["environment"] == runtime_patch.PATCH_TEST_ENVIRONMENT


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        (b"Everything is up to date.\n", "everything_up_to_date"),
        (b"not everything is up to date.\n", "unexpected_success_output"),
        (b"Everything is up to date.\nwarning\n", "unexpected_success_output"),
        (b"1 file pushed\n", "objects_uploaded"),
        (b"1 file pushed\nEverything is up to date.\n", "objects_uploaded"),
    ],
)
def test_dvc_push_normalization_requires_one_exact_success_line(
    stdout: bytes, expected: str
) -> None:
    assert runtime_patch._normalized_patch_dvc_push_result(stdout, b"", 0) == expected


def test_dvc_push_uses_the_fixed_repository_executable(payload: dict[str, Any]) -> None:
    command = runtime_patch.patch_dvc_remote_push_command(
        {"implementation_lock": {"dvc_remote_name": "gcsremote"}},
        payload["adopted_seed_bundle"],
    )

    assert command[0] == ".venv/bin/dvc"


def test_fixed_dvc_executable_rejects_a_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bin_directory = tmp_path / ".venv" / "bin"
    bin_directory.mkdir(parents=True)
    target = tmp_path / "dvc-shim"
    target.write_text("#!/bin/sh\n", encoding="utf-8")
    target.chmod(0o700)
    (bin_directory / "dvc").symlink_to(target)
    monkeypatch.setattr(runtime_patch, "PROJECT_ROOT", tmp_path)

    with pytest.raises(DevelopmentRuntimePatchError, match="not a regular executable"):
        runtime_patch._require_fixed_dvc_executable((".venv/bin/dvc", "push"))


def test_companion_dialect_covers_patch_lock_for_generic_precommit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    paths = {
        "lock": Path(PATCH_LOCK_PATH),
        "manifest": Path(
            "reports/closure_v1/00_protocol/development_runtime_patch_lock_manifest.json"
        ),
        "script": Path("src/experiments/lock_closure_development_runtime_patch.py"),
        "base_lock": Path(
            "reports/closure_v1/00_protocol/development_runtime_lock.json"
        ),
        "base_schema": Path(
            "configs/closure_v1/development_runtime_lock.schema.json"
        ),
        "patch_schema": Path(
            "configs/closure_v1/development_runtime_patch_lock.schema.json"
        ),
        "validator": Path("src/experiments/closure_development_runtime_patch.py"),
    }
    for name, path in paths.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{name}\n", encoding="utf-8")

    def record(path: Path, role: str) -> dict[str, Any]:
        return {
            "path": path.as_posix(),
            "role": role,
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    companion = {
        "manifest_version": "closure_development_runtime_patch_companion_manifest_v1",
        "status": "completed",
        "outputs": [record(paths["lock"], "external_development_runtime_patch_lock")],
        "script": record(paths["script"], "generating_script"),
        "inputs": [
            record(paths["base_lock"], "base_development_runtime_lock"),
            record(paths["base_schema"], "base_development_runtime_lock_schema"),
            record(paths["patch_schema"], "development_runtime_patch_lock_schema"),
            record(paths["validator"], "development_runtime_patch_validator"),
        ],
    }
    paths["manifest"].write_text(
        json.dumps(companion, indent=2) + "\n",
        encoding="utf-8",
    )

    findings = validate_experiment_manifests(
        staged_paths={paths["lock"], paths["manifest"]},
        artifacts=[],
        max_hash_bytes=1024 * 1024,
        verify_manifest_inputs=True,
    )

    assert not [finding for finding in findings if finding.level in {"fail", "warn"}]


def test_locker_execute_orders_checks_before_atomic_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    prelock = {
        "runtime": {},
        "adopted_seed_bundle": {},
        "publication_sequence": {},
    }
    snapshots = iter((prelock, prelock))
    monkeypatch.setattr(patch_locker, "_require_default_outputs", lambda *_a: None)
    monkeypatch.setattr(patch_locker, "_require_default_inputs", lambda **_k: None)
    guards = (object(), object())
    monkeypatch.setattr(
        patch_locker,
        "_acquire_output_guards",
        lambda *_a: events.append("guards") or guards,
    )
    monkeypatch.setattr(patch_locker, "_release_output_guard", lambda _guard: None)
    monkeypatch.setattr(
        patch_locker,
        "collect_patch_prelock_state",
        lambda **_k: events.append("collect") or next(snapshots),
    )
    monkeypatch.setattr(
        patch_locker,
        "command_evidence",
        lambda command: events.append(f"command:{Path(command[0]).name}")
        or {"command": list(command)},
    )
    monkeypatch.setattr(
        patch_locker,
        "_focused_test_evidence",
        lambda command: events.append(f"command:{Path(command[0]).name}")
        or {"command": list(command)},
    )
    monkeypatch.setattr(
        patch_locker,
        "verify_patch_dvc_remote_by_idempotent_push",
        lambda *_a: events.append("dvc") or {},
    )
    monkeypatch.setattr(
        patch_locker,
        "build_development_runtime_patch_lock_payload",
        lambda *_a, **_k: events.append("build") or {"lock": True},
    )
    monkeypatch.setattr(patch_locker, "load_json_mapping", lambda _path: {})
    monkeypatch.setattr(
        patch_locker,
        "validate_development_runtime_patch_lock_payload",
        lambda *_a: events.append("validate"),
    )
    monkeypatch.setattr(
        patch_locker,
        "_companion_manifest",
        lambda **_k: events.append("companion") or {"manifest": True},
    )
    monkeypatch.setattr(
        patch_locker,
        "_publish_guarded_json",
        lambda _payload, path, _guard: events.append(f"write:{path.name}")
        or patch_locker._OwnedPath(path, 1, len(events)),
    )
    monkeypatch.setattr(patch_locker, "_is_owned", lambda _owner: True)

    patch_locker.create_development_runtime_patch_lock(
        base_lock_path=patch_locker.DEFAULT_LOCK_PATH,
        base_lock_schema=patch_locker.DEFAULT_LOCK_SCHEMA,
        runtime_config=patch_locker.DEFAULT_RUNTIME_CONFIG,
        runtime_schema=patch_locker.DEFAULT_RUNTIME_SCHEMA,
        patch_lock_schema=patch_locker.DEFAULT_PATCH_LOCK_SCHEMA,
        output=patch_locker.DEFAULT_PATCH_LOCK_PATH,
        manifest_output=patch_locker.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        device="cpu",
        verify_dvc_remote_by_idempotent_push_flag=True,
    )

    assert events == [
        "guards",
        "collect",
        "command:ty",
        "command:pytest",
        "dvc",
        "collect",
        "build",
        "validate",
        "write:development_runtime_patch_lock.json",
        "companion",
        "write:development_runtime_patch_lock_manifest.json",
    ]


def test_publication_bundle_is_one_exact_direct_two_file_commit(
    payload: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publication_commit = "f" * 40
    lock_blob = b'{"lock":true}\n'
    components = {
        record["path"]: record for record in payload["patch_components"]["records"]
    }

    def with_role(record: dict[str, Any], role: str) -> dict[str, Any]:
        return {
            "path": record["path"],
            "role": role,
            "bytes": record["bytes"],
            "sha256": record["sha256"],
        }

    companion = {
        "manifest_version": "closure_development_runtime_patch_companion_manifest_v1",
        "status": "completed",
        "experiment_id": "closure_v1",
        "gate": "E0-DLP",
        "patch_id": "development_runtime_compatibility_patch_1",
        "created_at_utc": payload["created_at_utc"],
        "outputs": [
            {
                "path": PATCH_LOCK_PATH,
                "role": "external_development_runtime_patch_lock",
                "bytes": len(lock_blob),
                "sha256": hashlib.sha256(lock_blob).hexdigest(),
            }
        ],
        "script": with_role(
            components["src/experiments/lock_closure_development_runtime_patch.py"],
            "generating_script",
        ),
        "inputs": [
            with_role(payload["base_e0_dl"]["lock"], "base_development_runtime_lock"),
            with_role(
                payload["base_e0_dl"]["schema"],
                "base_development_runtime_lock_schema",
            ),
            with_role(
                components[
                    "configs/closure_v1/development_runtime_patch_lock.schema.json"
                ],
                "development_runtime_patch_lock_schema",
            ),
            with_role(
                components["src/experiments/closure_development_runtime_patch.py"],
                "development_runtime_patch_validator",
            ),
        ],
        "development_fit_authorized": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
        "authoritative_contract": False,
        "authoritative_lock_path": PATCH_LOCK_PATH,
    }
    companion_blob = (json.dumps(companion, indent=2) + "\n").encode("utf-8")
    lock_file = tmp_path / "lock.json"
    companion_file = tmp_path / "manifest.json"
    lock_file.write_bytes(lock_blob)
    companion_file.write_bytes(companion_blob)
    diff_calls: list[tuple[str, str, tuple[str, ...]]] = []

    monkeypatch.setattr(runtime_patch, "_introduced_commit", lambda _path: publication_commit)
    def fake_git(*args: str, **_kwargs: Any) -> str:
        if args and args[0] == "rev-list" and any(".." in arg for arg in args):
            return ""
        return f"{publication_commit} {payload['patch_repository']['head']}"

    monkeypatch.setattr(runtime_patch, "_git", fake_git)
    monkeypatch.setattr(runtime_patch, "_require_ancestor", lambda *_a: None)
    monkeypatch.setattr(
        runtime_patch,
        "_git_diff_exact",
        lambda base, head, *, expected_paths, expected_modified_paths: diff_calls.append(
            (base, head, tuple(expected_paths))
        )
        or {},
    )

    def fake_blob(_head: str, path: str) -> bytes | None:
        if path == PATCH_LOCK_PATH:
            return lock_blob
        if path == runtime_patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix():
            return companion_blob
        return None

    monkeypatch.setattr(runtime_patch, "_git_blob", fake_blob)
    monkeypatch.setattr(
        runtime_patch,
        "_read_regular_repository_bytes",
        lambda path, **_kwargs: (
            lock_file.read_bytes()
            if str(path) == PATCH_LOCK_PATH
            else companion_file.read_bytes()
        ),
    )

    observed = runtime_patch._validate_patch_publication_bundle(
        payload,
        execution_head=publication_commit,
        published_head=publication_commit,
    )

    assert observed == publication_commit
    assert diff_calls == [
        (
            payload["patch_repository"]["head"],
            publication_commit,
            (
                PATCH_LOCK_PATH,
                runtime_patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(),
            ),
        )
    ]


def test_published_gate_checks_lock_and_companion_status_together(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_git(*args: str, **_kwargs: Any) -> str:
        calls.append(args)
        return "?? reports/closure_v1/00_protocol/development_runtime_patch_lock_manifest.json"

    monkeypatch.setattr(runtime_patch, "_git", fake_git)

    with pytest.raises(DevelopmentRuntimePatchError, match="publication bundle is modified"):
        runtime_patch._require_patch_published(
            runtime_patch.DEFAULT_PATCH_LOCK_PATH,
            verify_remote=False,
        )

    assert calls == [
        (
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            PATCH_LOCK_PATH,
            runtime_patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(),
        )
    ]


def test_full_history_detects_modify_restore_hidden_behind_merge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    git("init", "-b", "main")
    git("config", "user.name", "E0-DLP test")
    git("config", "user.email", "e0-dlp@example.invalid")
    lock = tmp_path / "lock.json"
    companion = tmp_path / "manifest.json"
    lock.write_bytes(b"lock\n")
    companion.write_bytes(b"manifest\n")
    git("add", "lock.json", "manifest.json")
    git("commit", "-m", "P")
    publication = git("rev-parse", "HEAD")
    git("checkout", "-b", "restore-branch")
    lock.write_bytes(b"changed\n")
    git("add", "lock.json")
    git("commit", "-m", "Q changes lock")
    lock.write_bytes(b"lock\n")
    git("add", "lock.json")
    git("commit", "-m", "R restores lock")
    git("checkout", "main")
    (tmp_path / "unrelated.txt").write_text("main\n", encoding="utf-8")
    git("add", "unrelated.txt")
    git("commit", "-m", "main divergence")
    git("merge", "--no-ff", "restore-branch", "-m", "merge restored branch")
    descendant = git("rev-parse", "HEAD")
    monkeypatch.setattr(runtime_patch, "PROJECT_ROOT", tmp_path)

    touched = runtime_patch._git(
        "rev-list",
        "--full-history",
        f"{publication}..{descendant}",
        "--",
        "lock.json",
        "manifest.json",
    )

    assert touched


def test_public_validator_and_locker_reject_nondefault_paths() -> None:
    with pytest.raises(DevelopmentRuntimePatchError, match="closed default paths"):
        runtime_patch._require_default_validation_paths(
            patch_lock_path=Path("reports/closure_v1/00_protocol/other.json"),
            patch_lock_schema=runtime_patch.DEFAULT_PATCH_LOCK_SCHEMA,
            base_lock_path=runtime_patch.DEFAULT_LOCK_PATH,
            base_lock_schema=runtime_patch.DEFAULT_LOCK_SCHEMA,
            runtime_config=runtime_patch.DEFAULT_RUNTIME_CONFIG,
            runtime_schema=runtime_patch.DEFAULT_RUNTIME_SCHEMA,
        )
    with pytest.raises(DevelopmentRuntimePatchError, match="closed default paths"):
        patch_locker._require_default_inputs(
            base_lock_path=patch_locker.DEFAULT_LOCK_PATH,
            base_lock_schema=patch_locker.DEFAULT_LOCK_SCHEMA,
            runtime_config=Path("configs/closure_v1/other.yaml"),
            runtime_schema=patch_locker.DEFAULT_RUNTIME_SCHEMA,
            patch_lock_schema=patch_locker.DEFAULT_PATCH_LOCK_SCHEMA,
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "split_commit",
        "merge_parent",
        "lock_drift",
        "companion_drift",
        "historical_touch_then_restore",
    ],
)
def test_publication_bundle_rejects_chronology_or_descendant_byte_drift(
    mutation: str,
    payload: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publication_commit = "f" * 40
    execution_head = "9" * 40
    old_lock = b"old lock\n"
    old_companion = b"old companion\n"
    current_lock = b"new lock\n" if mutation == "lock_drift" else old_lock
    current_companion = (
        b"new companion\n" if mutation == "companion_drift" else old_companion
    )
    lock_file = tmp_path / "lock.json"
    companion_file = tmp_path / "manifest.json"
    lock_file.write_bytes(current_lock)
    companion_file.write_bytes(current_companion)

    def introduced(path: str) -> str:
        if mutation == "split_commit" and path.endswith("_manifest.json"):
            return "8" * 40
        return publication_commit

    monkeypatch.setattr(runtime_patch, "_introduced_commit", introduced)
    parent_line = f"{publication_commit} {payload['patch_repository']['head']}"
    if mutation == "merge_parent":
        parent_line += f" {'7' * 40}"
    def fake_git(*args: str, **_kwargs: Any) -> str:
        if args and args[0] == "rev-list" and any(".." in arg for arg in args):
            return "6" * 40 if mutation == "historical_touch_then_restore" else ""
        return parent_line

    monkeypatch.setattr(runtime_patch, "_git", fake_git)
    monkeypatch.setattr(runtime_patch, "_require_ancestor", lambda *_a: None)
    monkeypatch.setattr(runtime_patch, "_git_diff_exact", lambda *_a, **_k: {})

    def fake_blob(head: str, path: str) -> bytes | None:
        if path == PATCH_LOCK_PATH:
            return old_lock if head == publication_commit else current_lock
        if path == runtime_patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix():
            return old_companion if head == publication_commit else current_companion
        return None

    monkeypatch.setattr(runtime_patch, "_git_blob", fake_blob)
    monkeypatch.setattr(
        runtime_patch,
        "_read_regular_repository_bytes",
        lambda path, **_kwargs: (
            lock_file.read_bytes()
            if str(path) == PATCH_LOCK_PATH
            else companion_file.read_bytes()
        ),
    )

    with pytest.raises(DevelopmentRuntimePatchError):
        runtime_patch._validate_patch_publication_bundle(
            payload,
            execution_head=execution_head,
            published_head=execution_head,
        )
