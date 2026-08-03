#!/usr/bin/env python
"""Validate the derived Closure V1 E0-D runtime contract.

The externally sealed protocol remains authoritative.  This module closes
implementation details that were not supplied strictly by historical
ANFIS/PIPE runners: raw projection and hash-ranked sampling, one-to-one seed
slots, identical no-current-Chl-a input/target/rollout lineage, and the fixed
temporal profile.  It validates metadata and hashes only; it does not read
modeling rows or authorize fitting.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import unicodedata
from collections.abc import Mapping, Sequence, Set as AbstractSet
from pathlib import Path
from string import Formatter
from typing import Any, cast

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.experiments.closure_contract import (
    ClosureContractError,
    load_and_validate_analysis_plan,
    load_json_mapping,
    load_yaml_mapping,
    repository_relative,
    resolve_repo_path,
    validate_json_schema,
)
from src.experiments.closure_development_guard import DevelopmentGate, load_development_gate


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_CONFIG = Path("configs/closure_v1/development_runtime.yaml")
DEFAULT_RUNTIME_SCHEMA = Path("configs/closure_v1/development_runtime.schema.json")
DEFAULT_PROTOCOL_LOCK = Path("reports/closure_v1/00_protocol/protocol_lock.json")
DEFAULT_COMMON_ORIGIN = Path("data/closure_v1/common_origin_manifest.parquet")
DEFAULT_COMMON_ORIGIN_COMPLETION = Path(
    "reports/closure_v1/01_surface/common_origin_manifest.json"
)

RUNTIME_SCHEMA_VERSION = "closure_development_runtime_v1"
COMMON_ORIGIN_MANIFEST_VERSION = "closure_common_origin_manifest_v1"
EXPECTED_COMMON_ORIGIN_COUNTS: dict[str, Any] = {
    "rows": 29196,
    "intent_origins": 9732,
    "sites": 353,
    "target_evaluable_rows": 24242,
    "complete_targets_evaluable_origins": 6814,
    "intent_origins_by_role": {
        "training": 8352,
        "model_selection": 1061,
        "calibration_threshold": 319,
    },
}
EXPECTED_COMMON_ORIGIN_CODE_PATHS = (
    "src/experiments/build_common_origin_manifest.py",
    "src/experiments/build_closure_holdout.py",
    "src/experiments/closure_contract.py",
    "src/experiments/closure_development_guard.py",
    "src/pandas_utils.py",
)
EXPECTED_COMMON_ORIGIN_CONFIG_PATHS = (
    "configs/closure_v1/analysis_plan.yaml",
    "configs/closure_v1/analysis_plan.schema.json",
    "configs/closure_v1/surface_primary.yaml",
    "configs/closure_v1/surface_secondary.yaml",
    "configs/closure_v1/location_holdout.yaml",
    "configs/closure_v1/model_benchmark.yaml",
    "configs/closure_v1/experimental_matrix.yaml",
    "configs/counterfactual_planning_v1.yaml",
)
EXPECTED_COMMON_ORIGIN_SOURCE_PATHS = (
    "data/panel/panel_monthly_v0.parquet",
    "data/splits/monthly_model_splits_v0.parquet",
    "data/targets/monthly_targets_model_v0.parquet",
    "data/targets/target_manifest_v0.json",
    "data/splits/split_manifest.json",
)
EXPECTED_COMMON_ORIGIN_PANEL_PROJECTION = (
    "source_id",
    "site_id",
    "year_month",
    "mean_TP_ugL",
    "mean_TN_ugL",
    "mean_temperature_C",
    "mean_secchi_depth_m",
    "mean_turbidity_NTU",
    "mean_DO_mgL",
    "mean_pH",
)
EXPECTED_COMMON_ORIGIN_TARGET_PROJECTION = (
    "source_id",
    "site_id",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
)
EXPECTED_COMMON_ORIGIN_SCANS: dict[str, dict[str, Any]] = {
    "panel": {
        "materialized_rows": 42110,
        "returned_rows": 42110,
        "boundary_crossing_rows": 0,
        "role_counts": {
            "training": 36639,
            "model_selection": 3739,
            "calibration_threshold": 1732,
        },
    },
    "target_keys": {
        "materialized_rows": 81863,
        "returned_rows": 81397,
        "boundary_crossing_rows": 466,
        "role_counts": {
            "training": 71239,
            "model_selection": 6997,
            "calibration_threshold": 3161,
        },
    },
}
EXPECTED_COMMON_ORIGIN_ROLE_HORIZON_AVAILABILITY: list[dict[str, Any]] = [
    {"time_role": "calibration_threshold", "horizon_months": 1, "target_evaluable": False, "rows": 46},
    {"time_role": "calibration_threshold", "horizon_months": 1, "target_evaluable": True, "rows": 273},
    {"time_role": "calibration_threshold", "horizon_months": 2, "target_evaluable": False, "rows": 58},
    {"time_role": "calibration_threshold", "horizon_months": 2, "target_evaluable": True, "rows": 261},
    {"time_role": "calibration_threshold", "horizon_months": 3, "target_evaluable": False, "rows": 71},
    {"time_role": "calibration_threshold", "horizon_months": 3, "target_evaluable": True, "rows": 248},
    {"time_role": "model_selection", "horizon_months": 1, "target_evaluable": False, "rows": 250},
    {"time_role": "model_selection", "horizon_months": 1, "target_evaluable": True, "rows": 811},
    {"time_role": "model_selection", "horizon_months": 2, "target_evaluable": False, "rows": 249},
    {"time_role": "model_selection", "horizon_months": 2, "target_evaluable": True, "rows": 812},
    {"time_role": "model_selection", "horizon_months": 3, "target_evaluable": False, "rows": 241},
    {"time_role": "model_selection", "horizon_months": 3, "target_evaluable": True, "rows": 820},
    {"time_role": "training", "horizon_months": 1, "target_evaluable": False, "rows": 1213},
    {"time_role": "training", "horizon_months": 1, "target_evaluable": True, "rows": 7139},
    {"time_role": "training", "horizon_months": 2, "target_evaluable": False, "rows": 1336},
    {"time_role": "training", "horizon_months": 2, "target_evaluable": True, "rows": 7016},
    {"time_role": "training", "horizon_months": 3, "target_evaluable": False, "rows": 1490},
    {"time_role": "training", "horizon_months": 3, "target_evaluable": True, "rows": 6862},
]
EXPECTED_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
EXPECTED_PRIMARY_MODULES = ("ANFIS-N", "ANFIS-F", "ANFIS-T-no-current")
EXPECTED_MODULE_OFFSETS = {
    "ANFIS-N": 101,
    "ANFIS-F": 202,
    "ANFIS-T-no-current": 404,
}
CANONICAL_STATE_CHANNELS = (
    "yN",
    "yF",
    "yT",
    "sigma_N",
    "sigma_F",
    "sigma_T",
    "delta_yN",
    "delta_yF",
    "delta_yT",
)
SEASON_COLUMNS = (
    "season_sin_annual",
    "season_cos_annual",
    "season_sin_semiannual",
    "season_cos_semiannual",
)
EXPECTED_INPUT_COLUMNS = tuple(f"x_{column}" for column in CANONICAL_STATE_CHANNELS) + SEASON_COLUMNS
EXPECTED_TARGET_COLUMNS = tuple(f"target_{column}" for column in CANONICAL_STATE_CHANNELS)
EXPECTED_SEQUENCE_TABLE: dict[str, Any] = {
    "schema_version": "closure_pipe_sequence_v1",
    "row_unit": "one_row_per_common_origin",
    "expected_intent_rows": 9732,
    "expected_intent_rows_by_role": {
        "training": 8352,
        "model_selection": 1061,
        "calibration_threshold": 319,
    },
    "identity_columns": [
        "source_id",
        "site_id",
        "common_origin_id",
        "origin_year_month",
        "target_year_month",
        "time_role",
        "sequence_status",
        "failure_reason",
    ],
    "input_columns_source": "primary_autoregressive_state.input_columns",
    "input_physical_type": "fixed_size_list_float32_length_12",
    "input_history_order": "oldest_calendar_month_to_origin_month",
    "target_columns_source": "primary_autoregressive_state.target_columns",
    "target_physical_type": "float32_scalar",
    "target_month": "origin_plus_one_calendar_month",
    "status_values": [
        "success",
        "input_history_unavailable",
        "autoregressive_target_unavailable",
        "model_slot_unavailable",
    ],
    "success_tensor_policy": "all_13_input_lists_and_9_targets_finite",
    "failure_tensor_policy": "retain_identity_status_reason_and_nullable_tensors",
    "retention_policy": "retain_all_intent_origins_without_availability_filtering",
    "history_context_role_policy": "may_precede_endpoint_role_and_never_contributes_loss",
    "endpoint_role_policy": "origin_and_target_must_share_locked_role",
    "canonical_row_order": [
        "source_id_utf8_ascending",
        "site_id_utf8_ascending",
        "origin_year_month_ascending",
        "target_year_month_ascending",
    ],
    "forbidden_columns": ["split", "dataset_split", "x_irc1", "x_irc1_adaptive"],
    "observed_chla_columns_or_lineage": "forbidden",
}
EXPECTED_BATCH_ORDER_DIGEST: dict[str, Any] = {
    "algorithm": "sha256",
    "canonical_key_columns": [
        "source_id",
        "site_id",
        "origin_year_month",
        "target_year_month",
    ],
    "canonical_order_before_shuffle": "utf8_source_site_then_origin_target_ascending",
    "epoch_permutation": "torch_randperm_cpu_generator_seeded_base_seed_plus_one_based_epoch",
    "batch_record": "compact_json_array_epoch_batch_index_and_ordered_key_arrays",
    "json_serialization": "utf8_ensure_ascii_false_compact_separators",
    "record_framing": "one_lf_byte_after_each_batch_record",
    "includes_final_partial_batch": True,
}
EXPECTED_TRAINING_DEVICE_POLICY = {
    "cublas_workspace_config_if_cuda": "not_applicable_cpu_only_e0_dl_v1",
    "device_policy": "cpu_only_locked_by_e0_dl_v1",
    "automatic_device_selection": "forbidden",
    "cross_device_numerical_equivalence_claim": "forbidden",
}
EXPECTED_CHECKPOINT_ARTIFACT_LIFECYCLE: dict[str, Any] = {
    "checkpoint_payload": "unblended_raw_best_model_state",
    "provisional_blend_persisted_in_checkpoint": False,
    "final_model_payload": "restored_raw_best_model_state_plus_final_blend_metadata",
    "final_blend_recomputed_after_restore_exactly_once": True,
    "checkpoint_and_final_model_hashes_required": True,
}
EXPECTED_ROLLOUT_OUTPUT_TABLE: dict[str, Any] = {
    "schema_version": "closure_pipe_rollout_v1",
    "row_unit": "one_row_per_evaluation_unit_model_seed",
    "expected_rows_per_model_seed": 29196,
    "identity_columns": [
        "evaluation_unit_id",
        "common_origin_id",
        "model_id",
        "base_seed",
        "source_id",
        "site_id",
        "origin_year_month",
        "target_year_month",
        "horizon_months",
        "time_role",
        "prediction_status",
        "failure_reason",
        "origin_seed_hex",
        "predraw_sha256",
    ],
    "prediction_status_values": [
        "success",
        "sequence_unavailable",
        "model_unavailable",
        "rollout_failed",
    ],
    "state_sample_columns": [f"sample_{channel}" for channel in CANONICAL_STATE_CHANNELS],
    "state_sample_physical_type": "fixed_size_list_float32_length_128",
    "irc_sample_column": "irc_samples",
    "irc_sample_physical_type": "fixed_size_list_float64_length_128",
    "raw_bloom_score_column": "raw_bloom_score",
    "raw_bloom_score_physical_type": "float64",
    "failure_sample_policy": "retain_row_with_null_sample_lists_and_raw_score",
    "denominator_policy": "retain_all_29196_intent_rows_without_target_or_success_filtering",
    "shared_success_policy": "derive_later_from_paired_p0_p1_intersection",
    "canonical_row_order": [
        "source_id_utf8_ascending",
        "site_id_utf8_ascending",
        "origin_year_month_ascending",
        "horizon_months_ascending",
    ],
}
EXPECTED_CALIBRATION_RAW_SCORE: dict[str, Any] = {
    "column": "raw_bloom_score",
    "formula": "arithmetic_mean_of_128_trajectory_irc_values",
    "trajectory_irc_formula": "clip_0_1_of_yN_plus_1_minus_yF_plus_yT_divided_by_3",
    "calculation_dtype": "float64_from_float32_state_samples",
    "threshold_dependent": False,
    "model_selection_use": "choose_identity_platt_or_isotonic",
    "calibration_threshold_use": "refit_selected_method_and_select_f2_threshold",
}
EXPECTED_RUNTIME_COMPONENT_PATHS: dict[str, Any] = {
    "closure_development_guard": "src/experiments/closure_development_guard.py",
    "common_origin_builder": "src/experiments/build_common_origin_manifest.py",
    "runtime_contract_validator": "src/experiments/closure_runtime_contract.py",
    "strict_expert_state_adapter": "src/experiments/build_closure_expert_state.py",
    "strict_anfis_state_adapter": "src/experiments/fit_closure_anfis_state.py",
    "strict_sequence_adapter": "src/experiments/build_closure_pipe_sequences.py",
    "strict_temporal_fit_adapter": "src/experiments/train_closure_pipe.py",
    "strict_rollout_kernel": "src/experiments/rollout_closure_pipe.py",
    "runtime_lock_validator": "src/experiments/closure_development_runtime_lock.py",
    "runtime_locker": "src/experiments/lock_closure_development_runtime.py",
    "runtime_lock_schema": "configs/closure_v1/development_runtime_lock.schema.json",
    "dvc_ownership_overlay": "configs/closure_v1/dvc_artifacts_post_lock.yaml",
    "prepublication_artifact_validator": "src/data/prepare_commit_artifacts.py",
    "test_session_determinism": "tests/conftest.py",
    "relevant_tests": [
        "tests/test_closure_runtime_contract.py",
        "tests/test_build_closure_expert_state.py",
        "tests/test_fit_closure_anfis_state.py",
        "tests/test_build_closure_pipe_sequences.py",
        "tests/test_train_closure_pipe.py",
        "tests/test_rollout_closure_pipe.py",
        "tests/test_closure_development_runtime_lock.py",
        "tests/test_lock_closure_development_runtime.py",
        "tests/test_prepare_commit_artifacts.py",
        "tests/test_data_versioning_config.py",
        "tests/test_dvc_add_from_manifest.py",
    ],
    "pyproject": "pyproject.toml",
    "poetry_lock": "poetry.lock",
}
EXPECTED_RUNTIME_PARENT_PATHS: dict[str, str] = {
    "protocol_lock": "reports/closure_v1/00_protocol/protocol_lock.json",
    "holdout_assignment": "data/closure_v1/closure_holdout_assignment.csv",
    "holdout_manifest": "reports/closure_v1/00_protocol/holdout_manifest.json",
    "common_origin": "data/closure_v1/common_origin_manifest.parquet",
    "common_origin_completion_manifest": "reports/closure_v1/01_surface/common_origin_manifest.json",
    "runtime_config": "configs/closure_v1/development_runtime.yaml",
    "runtime_schema": "configs/closure_v1/development_runtime.schema.json",
    "expert_state": "data/closure_v1/development/expert/expert_no_current_state.parquet",
    "expert_state_manifest": "reports/closure_v1/01_surface/expert/expert_no_current_state_manifest.json",
    "expert_state_lineage_audit": "reports/closure_v1/01_surface/expert/expert_no_current_state_lineage_audit.json",
    "expert_state_dvc_pointer": "data/closure_v1/development/expert/expert_no_current_state.parquet.dvc",
    "restored_panel": "data/panel/panel_monthly_v0.parquet",
    "restored_expert_anchor": "data/fuzzy/state_vector_v0.parquet",
}
EXPECTED_RUNTIME_COMPONENT_ROLES = tuple(EXPECTED_RUNTIME_COMPONENT_PATHS)
EXPECTED_RUNTIME_PARENT_HASH_ROLES = (
    "protocol_lock",
    "holdout_assignment",
    "holdout_manifest",
    "common_origin",
    "common_origin_completion_manifest",
    "runtime_config",
    "runtime_schema",
    "expert_state",
    "expert_state_manifest",
    "expert_state_lineage_audit",
    "expert_state_dvc_pointer",
    "restored_panel",
    "restored_expert_anchor",
    "planned_artifact_paths",
    "runtime_transitive_source_dependencies",
)
EXPECTED_RUNTIME_LEGACY_DEPENDENCY_PATHS = (
    "src/fuzzy/expert.py",
    "src/fuzzy/adaptive_anfis.py",
    "src/pandas_utils.py",
    "src/experiments/run_adaptive_anfis_real_smoke.py",
    "src/experiments/build_pipe_sequences.py",
    "src/experiments/train_pipe_grud.py",
    "src/experiments/rollout_pipe_grud.py",
)
EXPECTED_RUNTIME_AUTHORIZATION = {
    "development_fit_authorized": True,
    "evaluation_authorized": False,
    "e0_u_authorized": False,
}
EXPECTED_CPU_EXECUTION_POLICY = {
    "device": "cpu",
    "torch_num_threads": 1,
    "torch_num_interop_threads": 1,
    "blas_thread_environment_control": "not_locked_by_e0_dl_v1",
    "bitwise_reproducibility_claim": (
        "forbidden_across_processes_or_blas_backends"
    ),
}
EXPECTED_RUNTIME_CANONICAL_ORIGIN_IDENTITY = {
    "remote_name": "origin",
    "algorithm": "git_remote_host_path_v1_sha256_utf8",
    "expected_identity_sha256": (
        "475fdf8ad6839d3d291010ff999b4e4c0f8604a0e8d8a09fcebe5ccb843d1905"
    ),
    "require_fetch_push_identity_match": True,
}
EXPECTED_P0_STATE_MAPPING = {
    "yN": "yN",
    "yF": "yF",
    "yT": "yT_no_chla",
    "sigma_N": "sigma_N",
    "sigma_F": "sigma_F",
    "sigma_T": "sigma_T_no_chla",
    "delta_yN": "delta_yN",
    "delta_yF": "delta_yF",
    "delta_yT": "delta_yT_no_chla",
}
EXPECTED_P1_STATE_MAPPING = {
    "yN": "yN_adaptive",
    "yF": "yF_adaptive",
    "yT": "yT_no_chla_adaptive",
    "sigma_N": "sigma_N_adaptive",
    "sigma_F": "sigma_F_adaptive",
    "sigma_T": "sigma_T_no_chla_adaptive",
    "delta_yN": "delta_yN_adaptive",
    "delta_yF": "delta_yF_adaptive",
    "delta_yT": "delta_yT_no_chla_adaptive",
}
EXPECTED_TARGET_TO_NEXT_INPUT_MAPPING: dict[str, str] = {
    f"target_{column}": f"x_{column}" for column in CANONICAL_STATE_CHANNELS
}
EXPECTED_ANFIS_CONFIGURATION: dict[str, Any] = {
    "train_rows_per_module": 4096,
    "memberships_per_input": 3,
    "center_constraint": "unit",
    "epochs": 60,
    "learning_rate": 0.03,
    "min_width": 0.03,
    "min_gap": 0.0001,
    "grad_clip": 1.0,
    "optimizer": "AdamW",
    "weight_decay": 0.0,
    "loss": "full_batch_anchor_mse",
    "output_activation": "sigmoid",
    "feature_imputation_value": 0.5,
    "feature_clip": [0.0, 1.0],
    "max_train_missing_fraction": 0.5,
    "min_output_standard_deviation": 0.0001,
    "predict_batch_rows": 32768,
}
EXPECTED_ANFIS_INITIALIZATION = {
    "initial_width": 0.25,
    "unit_center_margin": 0.05,
    "consequent_weight": 0.0,
    "consequent_bias": 0.0,
    "normalized_firing_strength_floor": 1e-12,
}
EXPECTED_ANFIS_UNCERTAINTY_PROXY: dict[str, Any] = {
    "base": 0.10,
    "normalized_rule_entropy_weight": 0.45,
    "missing_fraction_weight": 0.35,
    "clip": [0.0, 1.0],
    "normalized_firing_strength_formula": "firing/max(sum_firing,1e-12)",
    "firing_input": "unnormalized_model_rule_firing_strengths",
    "model_firing_dtype": "float32",
    "firing_cast_before_sum": "quantize_float32_then_cast_float64",
    "firing_input_range": [0.0, 1.0],
    "firing_sum_floor": 1e-12,
    "all_zero_firing_policy": "zero_entropy",
    "strict_adapter_uncertainty_api": "module_aware_exact_rule_count",
    "entropy_formula": "-sum(p*ln(clip(p,1e-12,1)))",
    "entropy_probability_clip": [1e-12, 1.0],
    "entropy_normalization": "divide_by_ln_rule_count_when_rule_count_gt_1",
    "single_rule_entropy": 0.0,
    "missing_fraction_formula": "missing_module_features_before_imputation/module_feature_count",
    "calculation_dtype_after_model_firing": "float64",
    "rule_count_by_module": {"ANFIS-N": 27, "ANFIS-F": 81, "ANFIS-T-no-current": 3},
    "golden_vectors": [
        {
            "firing_strengths": [0.25, 0.25],
            "rule_count": 2,
            "missing_fraction": 0.5,
            "sigma": 0.725,
        },
        {
            "firing_strengths": [1.0],
            "rule_count": 1,
            "missing_fraction": 0.25,
            "sigma": 0.1875,
        },
        {
            "firing_strengths": [0.0, 0.0],
            "rule_count": 2,
            "missing_fraction": 0.0,
            "sigma": 0.1,
        },
    ],
}
EXPECTED_ANFIS_REFERENCE_SHA256 = "84644b764d921d4becfbb216e46e33707337fd22d72cf02064b707804953710d"
EXPECTED_PIPE_REFERENCE_SHA256 = "01f2cf62811ba450c0639c922a5f9faa2a92d9100f8589307d386441bf4b88ca"
EXPECTED_TARGET_MANIFEST_SHA256 = "5c082cf12aa4f9c6350f4e44eb2b41c7f0dc52cb041c3a67c09cd8e286f17ca4"
EXPECTED_TARGET_ARTIFACT_SHA256 = "c93ee8dbf424828c8dc11bc5da236d5c505e5f6ba7478eb689cca12a88c7e799"
EXPECTED_PANEL_SHA256 = "8aedc531b9e024bd8f73e66f917932b8301f79309d4596618c5a839e3b70dc62"
EXPECTED_EXPERT_STATE_SHA256 = "81ba2af85fe949c683fdc50a044d0d882ee0f6fa6d68eb36619de1be800649a6"
EXPECTED_PROTOCOL_LOCK_SHA256 = "7b6530dd3b918a61b55e26b54d5cd68919e9cf6919e3521b452f7b05e2ded9c6"
EXPECTED_HOLDOUT_ASSIGNMENT_SHA256 = "b090994b9ec9a3cd6af8e3261879872a12efe301e02fe1727ded519b46ebedef"
EXPECTED_HOLDOUT_MANIFEST_SHA256 = "b05e7767c35630806258494bcfac49ac26f7e628fea5d4185c5f9545ca480bc1"
EXPECTED_ANFIS_SAMPLING = {
    "key_columns": ["source_id", "site_id", "year_month"],
    "algorithm": "sha256_rank_json_v1",
    "strict_adapter_sampler_api": "anfis_hash_rank_sample_without_size_override",
    "module_seed_formula": "base_seed_plus_module_offset",
    "candidate_pipeline_order": [
        "raw_projection_at_parquet_read",
        "development_assignment_and_training_role_filter_on_both_inputs",
        "expert_anchor_inner_join_one_to_one",
        "allowed_derived_feature_construction",
        "finite_non_null_module_anchor_filter",
        "per_module_feature_missingness_filter",
        "sha256_rank",
    ],
    "candidate_eligibility": {
        "source_id": "wqp",
        "assignment_role": "development",
        "time_role": "training",
        "latest_year_month": "2018-12",
        "module_anchor": "finite_unit_interval",
        "maximum_module_feature_missing_fraction": 0.5,
        "missingness_denominator": "exact_module_feature_count",
    },
    "development_membership_source": "closure_development_guard.development_keys",
    "development_membership_rechecked_in_sampler": True,
    "string_normalization": "require_unicode_nfc_without_rewrite",
    "year_month_normalization": "strict_yyyy_mm",
    "json_serialization": "utf8_ensure_ascii_false_compact_separators",
    "digest_record_framing": "one_lf_byte_after_each_json_record",
    "rank_payload": "compact_json_array_module_seed_source_id_site_id_year_month",
    "rank_digest": "sha256_utf8",
    "rank_order": [
        "rank_sha256_ascending",
        "source_id_utf8_ascending",
        "site_id_utf8_ascending",
        "year_month_ascending",
    ],
    "selected_rows": 4096,
    "replacement": False,
    "duplicate_key_policy": "fail",
    "selection_uses_outcomes": False,
    "insufficient_rows_policy": "model_unavailable_without_replacement",
    "candidate_universe_order": "compact_json_utf8_bytes_ascending",
    "candidate_universe_digest": "sha256_lf_delimited_compact_json_keys",
    "selected_key_order": "rank_order",
    "selected_keys_digest": "sha256_lf_delimited_compact_json_keys",
    "persisted_sample_columns": [
        "source_id",
        "site_id",
        "year_month",
        "module",
        "module_seed",
        "rank_sha256",
    ],
    "persisted_manifest_fields": [
        "input_rows",
        "excluded_nonfinite_target_rows",
        "excluded_missingness_rows",
        "eligible_universe_rows",
        "eligible_universe_sha256",
        "selected_rows",
        "selected_keys_sha256",
        "module",
        "base_seed",
        "module_seed",
    ],
}
EXPECTED_ANFIS_PANEL_COLUMNS = (
    "source_id",
    "site_id",
    "year_month",
    "mean_TP_ugL",
    "mean_TN_ugL",
    "TN_TP_ratio",
    "mean_DO_mgL",
    "mean_pH",
    "mean_turbidity_NTU",
    "mean_secchi_depth_m",
    "mean_temperature_C",
)
EXPECTED_ANFIS_ANCHOR_COLUMNS = ("source_id", "site_id", "year_month", "yN", "yF", "yT_no_chla")
EXPECTED_ANFIS_FEATURE_LINEAGE = {
    "tp_pressure": ["mean_TP_ugL"],
    "tn_pressure": ["mean_TN_ugL"],
    "ratio_imbalance_pressure": ["TN_TP_ratio"],
    "do_good": ["mean_DO_mgL"],
    "ph_good": ["mean_pH"],
    "turbidity_good": ["mean_turbidity_NTU"],
    "secchi_good": ["mean_secchi_depth_m"],
    "temp_favorable": ["mean_temperature_C"],
}
EXPECTED_ANFIS_FEATURE_TRANSFORMATIONS = {
    "numeric_policy": "coerce_invalid_or_nonfinite_to_missing",
    "output_dtype": "float64",
    "output_clip": [0.0, 1.0],
    "tp_pressure": {
        "operation": "log_ramp_up",
        "source": "mean_TP_ugL",
        "low": 10.0,
        "high": 100.0,
        "epsilon": 0.1,
        "negative_input": "missing",
    },
    "tn_pressure": {
        "operation": "log_ramp_up",
        "source": "mean_TN_ugL",
        "low": 300.0,
        "high": 1500.0,
        "epsilon": 0.1,
        "negative_input": "missing",
    },
    "ratio_imbalance_pressure": {
        "operation": "max",
        "source": "TN_TP_ratio",
        "components": [
            {"operation": "ramp_down", "low": 8.0, "high": 16.0},
            {"operation": "ramp_up", "low": 50.0, "high": 100.0},
        ],
    },
    "do_good": {
        "operation": "trapezoid",
        "source": "mean_DO_mgL",
        "a": 5.0,
        "b": 7.0,
        "c": 12.0,
        "d": 15.0,
    },
    "ph_good": {
        "operation": "trapezoid",
        "source": "mean_pH",
        "a": 6.5,
        "b": 7.0,
        "c": 8.6,
        "d": 9.5,
    },
    "turbidity_good": {
        "operation": "ramp_down",
        "source": "mean_turbidity_NTU",
        "low": 5.0,
        "high": 50.0,
    },
    "secchi_good": {
        "operation": "ramp_up",
        "source": "mean_secchi_depth_m",
        "low": 0.5,
        "high": 3.0,
    },
    "temp_favorable": {
        "operation": "trapezoid",
        "source": "mean_temperature_C",
        "a": 15.0,
        "b": 22.0,
        "c": 30.0,
        "d": 35.0,
    },
}
EXPECTED_ANFIS_MODULE_FEATURES = {
    "ANFIS-N": ("tp_pressure", "tn_pressure", "ratio_imbalance_pressure"),
    "ANFIS-F": ("do_good", "ph_good", "turbidity_good", "secchi_good"),
    "ANFIS-T-no-current": ("temp_favorable",),
}
EXPECTED_ANFIS_MODULE_TARGETS = {
    "ANFIS-N": "yN",
    "ANFIS-F": "yF",
    "ANFIS-T-no-current": "yT_no_chla",
}
EXPECTED_ANFIS_PANEL_ANCHOR_JOIN = {
    "key_columns": ["source_id", "site_id", "year_month"],
    "left_frame": "expert_anchor",
    "join_type": "inner",
    "relationship": "one_to_one",
    "duplicate_key_policy": "fail_on_either_input",
    "unmatched_anchor_policy": "exclude_and_count",
    "unmatched_panel_policy": "exclude_and_count",
    "output_order": "source_id_utf8_site_id_utf8_year_month_ascending",
    "manifest_alignment_counts": "required",
    "key_digest_serialization": "sha256_lf_delimited_compact_json_keys",
    "manifest_fields": [
        "filtered_anchor_rows",
        "filtered_panel_rows",
        "matched_rows",
        "unmatched_anchor_rows",
        "unmatched_panel_rows",
        "anchor_keys_sha256",
        "panel_keys_sha256",
        "matched_keys_sha256",
        "unmatched_anchor_keys_sha256",
        "unmatched_panel_keys_sha256",
    ],
    "conservation_equations": [
        "filtered_anchor_rows=matched_rows+unmatched_anchor_rows",
        "filtered_panel_rows=matched_rows+unmatched_panel_rows",
    ],
}
EXPECTED_TEMPORAL_ARCHITECTURE = {
    "family": "residual_probabilistic_gru",
    "canonical_grud": False,
    "history_length_months": 12,
    "input_dimension": 13,
    "target_dimension": 9,
    "hidden_dimension": 96,
    "recurrent_layers": 1,
    "dropout": 0.0,
    "batch_first": True,
    "residual_mode": "add_last",
}
EXPECTED_LOCKED_PIPE_ARCHITECTURE = {
    "history_length_months": 12,
    "input_dimension": 13,
    "hidden_dimension": 96,
    "recurrent_layers": 1,
    "residual_mode": "add_last",
    "batch_size": 2048,
    "maximum_epochs": 20,
    "early_stopping_patience_epochs": 5,
    "early_stopping_minimum_delta": 0.0,
    "selection_profile": "balanced",
}
EXPECTED_OUTCOME_SOURCES = {
    "future_chla_ugL": "future_chlorophyll_a_ugL",
    "bloom_h": "bloom_h",
    "future_risk": "target_risk_chla_h",
    "future_operational_trophic_state": "target_trophic_state_h",
}
EXPECTED_DELTA_SOURCE_COLUMNS = {
    "P0": ("yN", "yF", "yT_no_chla"),
    "P1": ("yN_adaptive", "yF_adaptive", "yT_no_chla_adaptive"),
}
EXPECTED_SEASONALITY = {
    "calendar_month_indexing": "one_based_1_to_12",
    "phase_formula": "r=2*pi*(calendar_month-1)/12",
    "season_sin_annual": "sin(r)",
    "season_cos_annual": "cos(r)",
    "season_sin_semiannual": "sin(2*r)",
    "season_cos_semiannual": "cos(2*r)",
    "calculation_precision": "float64",
    "model_cast": "float32_after_calculation",
}
EXPECTED_ROLLOUT_RNG: dict[str, Any] = {
    "algorithm": "numpy.random.PCG64",
    "generator_initialization": "numpy.random.Generator(numpy.random.PCG64(origin_seed))",
    "environment_version_locked_by_e0_dl": True,
    "origin_seed_payload": "compact_json_array_closure_v1_base_seed_source_id_site_id_origin_year_month",
    "origin_seed_digest": "sha256_utf8_first_128_bits_big_endian",
    "model_id_in_origin_seed_payload": False,
    "common_random_numbers": "shared_between_p0_p1_within_seed_slot",
    "generator_scope": "reinitialize_once_per_origin",
    "standard_normal_predraw_shape": [3, 128, 9],
    "draw_dtype": "float64",
    "draw_order": "horizon_major_sample_major_state_channel_order",
    "origin_processing_order": "source_id_utf8_site_id_utf8_origin_year_month_ascending",
    "batch_order_invariant": True,
    "origin_seed_records_required": True,
    "predraw_serialization": "little_endian_float64_c_order",
    "golden_predraw": {
        "base_seed": 1729,
        "source_id": "wqp",
        "site_id": "A",
        "origin_year_month": "2020-01",
        "sha256": "2ca072ae692d490fe43974edd9bb87fc71ddc57140d8bc0779fa13df75028a20",
    },
}
EXPECTED_ROLLOUT_STATE_CLIP = {
    "yN": [0.0, 1.0],
    "yF": [0.0, 1.0],
    "yT": [0.0, 1.0],
    "sigma_N": [0.0, 1.0],
    "sigma_F": [0.0, 1.0],
    "sigma_T": [0.0, 1.0],
    "delta_yN": [-1.0, 1.0],
    "delta_yF": [-1.0, 1.0],
    "delta_yT": [-1.0, 1.0],
}
EXPECTED_ROLLOUT_KERNEL: dict[str, Any] = {
    "output_blend_formula": "mu_blend=persistence+w*(mu-persistence)",
    "log_variance_clip": [-10.0, 2.0],
    "standard_deviation_formula": "sigma=exp(0.5*clipped_log_variance)",
    "stochastic_state_formula": "sampled_state=mu_blend+sigma*epsilon",
    "epsilon_indexing": "predraw[horizon_index,sample_index,state_channel_index]",
    "state_clip_stage": "per_channel_after_sampling_before_recycling",
    "trajectory_recycling": "each_sample_path_independently",
    "aggregate_or_mean_state_recycling": "forbidden",
    "seasonality_update": "target_calendar_month_after_state_clip",
    "window_update": "drop_oldest_then_append_sampled_state_plus_target_seasonality",
    "horizon_step_months": 1,
    "model_input_dtype": "float32",
    "model_output_dtype": "float32",
    "model_outputs_and_persistence_cast_before_arithmetic": "quantize_float32_then_cast_float64",
    "epsilon_dtype": "float64",
    "blend_variance_sampling_dtype": "float64_after_casting_model_outputs_and_persistence",
    "clip_dtype": "float64",
    "recycled_state_cast": "float32_after_clip_before_window_append",
    "seasonality_cast": "float64_calculation_then_float32_before_window_append",
    "next_model_window_dtype": "float32",
    "recursive_golden_vector": {
        "channel": "yN",
        "initial_persistence": 0.2,
        "mu": [0.6, 0.4],
        "log_variance": [-2.0, -1.0],
        "blend_weight": [0.5, 0.5],
        "epsilon": [0.1, -0.2],
        "recycled_float32_states": [
            0.4367879629135132,
            0.2970878481864929,
        ],
    },
}
ALLOWED_RUNTIME_ARTIFACT_ROOTS = (
    "data/closure_v1",
    "models/closure_v1",
    "reports/closure_v1",
)
EXPECTED_PLANNED_ARTIFACT_PATH_COUNT = 201
EXPECTED_PLANNED_ARTIFACT_PATHS_SHA256 = (
    "833fe57a573db135357a596949728fd0b6a436997ece0ba2c5555b815a42672c"
)
LOCKED_F1_MODULE_NAMES = ("ANFIS_N", "ANFIS_F", "ANFIS_T_no_current_chla")
STRICT_YEAR_MONTH = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")


class ClosureRuntimeContractError(ClosureContractError):
    """Raised when a derived E0-D decision drifts from its closed contract."""


def _sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mapping(payload: Mapping[str, Any], key: str, *, context: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ClosureRuntimeContractError(f"{context}.{key} must be a mapping")
    return value


def _sequence(payload: Mapping[str, Any], key: str, *, context: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ClosureRuntimeContractError(f"{context}.{key} must be an array")
    return list(value)


def _require_equal(observed: Any, expected: Any, *, context: str) -> None:
    if observed != expected:
        raise ClosureRuntimeContractError(
            f"{context} differs from the Closure V1 runtime contract: "
            f"observed={observed!r}, expected={expected!r}"
        )


def _require_typed_equal(observed: Any, expected: Any, *, context: str) -> None:
    if type(observed) is not type(expected):
        raise ClosureRuntimeContractError(
            f"{context} has the wrong scalar/container type: "
            f"observed={type(observed).__name__}, expected={type(expected).__name__}"
        )
    if isinstance(expected, dict):
        if set(observed) != set(expected):
            raise ClosureRuntimeContractError(f"{context} has different mapping keys")
        for key, expected_value in expected.items():
            _require_typed_equal(
                observed[key],
                expected_value,
                context=f"{context}.{key}",
            )
        return
    if isinstance(expected, list):
        if len(observed) != len(expected):
            raise ClosureRuntimeContractError(f"{context} has a different array length")
        for index, (observed_value, expected_value) in enumerate(
            zip(observed, expected, strict=True)
        ):
            _require_typed_equal(
                observed_value,
                expected_value,
                context=f"{context}[{index}]",
            )
        return
    if observed != expected:
        _require_equal(observed, expected, context=context)


def _require_exact_mapping(observed: Mapping[str, Any], expected: Mapping[str, Any], *, context: str) -> None:
    _require_equal(dict(observed), dict(expected), context=context)


def configure_torch_cpu_execution_policy(
    runtime: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply and verify the closed single-thread Torch CPU policy."""
    policy = _mapping(runtime, "cpu_execution_policy", context="development_runtime")
    _require_exact_mapping(
        policy,
        EXPECTED_CPU_EXECUTION_POLICY,
        context="CPU execution policy",
    )
    from src.fuzzy.adaptive_anfis import _require_torch  # noqa: PLC0415

    torch = _require_torch()
    if int(torch.get_num_threads()) != 1:
        torch.set_num_threads(1)
    if int(torch.get_num_interop_threads()) != 1:
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError as exc:
            raise ClosureRuntimeContractError(
                "Torch inter-op threads cannot be locked after parallel work started"
            ) from exc
    observed = {
        **dict(policy),
        "torch_num_threads_observed": int(torch.get_num_threads()),
        "torch_num_interop_threads_observed": int(torch.get_num_interop_threads()),
    }
    if (
        observed["torch_num_threads_observed"] != 1
        or observed["torch_num_interop_threads_observed"] != 1
    ):
        raise ClosureRuntimeContractError("Torch CPU thread policy was not applied exactly")
    return observed


def validate_autoregressive_state_mapping(model_id: str, mapping: Mapping[str, Any]) -> dict[str, str]:
    """Validate a model-facing state mapping for both inputs and targets."""
    expected_by_model = {
        "P0": EXPECTED_P0_STATE_MAPPING,
        "P1": EXPECTED_P1_STATE_MAPPING,
    }
    expected = expected_by_model.get(model_id)
    if expected is None:
        raise ClosureRuntimeContractError(f"Unsupported Closure autoregressive model: {model_id}")
    if any(not isinstance(key, str) or not isinstance(value, str) for key, value in mapping.items()):
        raise ClosureRuntimeContractError(f"{model_id} state mapping keys and values must be strings")
    normalized = {key: cast(str, value) for key, value in mapping.items()}
    _require_exact_mapping(normalized, expected, context=f"{model_id} state mapping")
    return normalized


def validate_seed_slots(slots: Sequence[Any]) -> list[dict[str, int]]:
    """Require five ordered one-to-one ANFIS/P0/P1 seed slots."""
    if len(slots) != len(EXPECTED_SEEDS):
        raise ClosureRuntimeContractError("Runtime seed plan must contain exactly five ordered slots")
    normalized: list[dict[str, int]] = []
    for index, (raw_slot, expected_seed) in enumerate(zip(slots, EXPECTED_SEEDS, strict=True), start=1):
        if not isinstance(raw_slot, Mapping):
            raise ClosureRuntimeContractError(f"Runtime seed slot {index} must be a mapping")
        expected_key_order = (
            "slot",
            "base_seed",
            "anfis_base_seed",
            "p0_model_seed",
            "p1_model_seed",
        )
        if set(raw_slot) != set(expected_key_order):
            raise ClosureRuntimeContractError(f"Runtime seed slot {index} has an unexpected schema")
        if any(type(raw_slot[key]) is not int for key in expected_key_order):
            raise ClosureRuntimeContractError(
                f"Runtime seed slot {index} values must be exact integers"
            )
        slot = {key: cast(int, raw_slot[key]) for key in expected_key_order}
        expected_slot = {
            "slot": index,
            "base_seed": expected_seed,
            "anfis_base_seed": expected_seed,
            "p0_model_seed": expected_seed,
            "p1_model_seed": expected_seed,
        }
        _require_equal(slot, expected_slot, context=f"runtime seed slot {index}")
        normalized.append(slot)
    return normalized


def anfis_module_substreams(base_seed: int) -> dict[str, int]:
    """Return the fixed primary-module substreams for one paired seed slot."""
    if type(base_seed) is not int or base_seed not in EXPECTED_SEEDS:
        raise ClosureRuntimeContractError(f"Unregistered Closure V1 seed: {base_seed}")
    return {module: int(base_seed + offset) for module, offset in EXPECTED_MODULE_OFFSETS.items()}


def _strict_identity_string(row: Mapping[str, Any], column: str) -> str:
    value = row.get(column)
    if not isinstance(value, str):
        raise ClosureRuntimeContractError(f"Closure key {column!r} must be a string")
    if not value or value != value.strip():
        raise ClosureRuntimeContractError(
            f"Closure key {column!r} must be non-empty without surrounding whitespace"
        )
    if unicodedata.normalize("NFC", value) != value:
        raise ClosureRuntimeContractError(
            f"Closure key {column!r} must already be Unicode NFC; rewriting immutable keys is forbidden"
        )
    return value


def _strict_sample_key(
    row: Mapping[str, Any],
    *,
    month_column: str = "year_month",
) -> tuple[str, str, str]:
    source_id = _strict_identity_string(row, "source_id")
    site_id = _strict_identity_string(row, "site_id")
    year_month = _strict_identity_string(row, month_column)
    if not STRICT_YEAR_MONTH.fullmatch(year_month):
        raise ClosureRuntimeContractError(f"Closure key {month_column!r} must use strict YYYY-MM")
    return source_id, site_id, year_month


def _compact_json_bytes(values: Sequence[Any]) -> bytes:
    return json.dumps(list(values), ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _optional_finite_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _clip_unit(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def _ramp_up(value: float, low: float, high: float) -> float:
    return _clip_unit((value - low) / (high - low))


def _ramp_down(value: float, low: float, high: float) -> float:
    return _clip_unit(1.0 - (value - low) / (high - low))


def _trapezoid(value: float, a: float, b: float, c: float, d: float) -> float:
    if b <= value <= c:
        return 1.0
    return min(_ramp_up(value, a, b), _ramp_down(value, c, d))


def closure_anfis_features(row: Mapping[str, Any]) -> dict[str, float | None]:
    """Apply the exact Chl-a-free raw-to-ANFIS feature transformations."""
    raw = {
        column: _optional_finite_float(row.get(column))
        for column in EXPECTED_ANFIS_PANEL_COLUMNS[3:]
    }
    tp = raw["mean_TP_ugL"]
    tn = raw["mean_TN_ugL"]
    ratio = raw["TN_TP_ratio"]
    dissolved_oxygen = raw["mean_DO_mgL"]
    ph = raw["mean_pH"]
    turbidity = raw["mean_turbidity_NTU"]
    secchi = raw["mean_secchi_depth_m"]
    temperature = raw["mean_temperature_C"]

    def log_ramp(value: float | None, low: float, high: float) -> float | None:
        if value is None or value < 0.0:
            return None
        epsilon = 0.1
        return _ramp_up(
            math.log(value + epsilon),
            math.log(low + epsilon),
            math.log(high + epsilon),
        )

    return {
        "tp_pressure": log_ramp(tp, 10.0, 100.0),
        "tn_pressure": log_ramp(tn, 300.0, 1500.0),
        "ratio_imbalance_pressure": (
            None
            if ratio is None
            else max(_ramp_down(ratio, 8.0, 16.0), _ramp_up(ratio, 50.0, 100.0))
        ),
        "do_good": None if dissolved_oxygen is None else _trapezoid(dissolved_oxygen, 5.0, 7.0, 12.0, 15.0),
        "ph_good": None if ph is None else _trapezoid(ph, 6.5, 7.0, 8.6, 9.5),
        "turbidity_good": None if turbidity is None else _ramp_down(turbidity, 5.0, 50.0),
        "secchi_good": None if secchi is None else _ramp_up(secchi, 0.5, 3.0),
        "temp_favorable": None if temperature is None else _trapezoid(temperature, 15.0, 22.0, 30.0, 35.0),
    }


def validate_anfis_raw_projection_columns(
    panel_columns: Sequence[str],
    expert_anchor_columns: Sequence[str],
) -> None:
    """Reject any physical ANFIS read projection that is not the exact allowlist."""
    _require_equal(
        tuple(panel_columns),
        EXPECTED_ANFIS_PANEL_COLUMNS,
        context="ANFIS panel physical projection",
    )
    _require_equal(
        tuple(expert_anchor_columns),
        EXPECTED_ANFIS_ANCHOR_COLUMNS,
        context="ANFIS expert-anchor physical projection",
    )


def _anfis_uncertainty_proxy(
    rule_firing_strengths: Sequence[float],
    *,
    expected_rule_count: int,
    missing_fraction: float,
) -> float:
    """Compute the closed float64 entropy/missingness uncertainty proxy."""
    if len(rule_firing_strengths) != expected_rule_count:
        raise ClosureRuntimeContractError(
            f"ANFIS uncertainty requires exactly {expected_rule_count} rule firing strengths"
        )
    firings: list[float] = []
    for value in rule_firing_strengths:
        if isinstance(value, bool):
            raise ClosureRuntimeContractError("ANFIS firing strengths must be finite in [0, 1]")
        try:
            firing = float(value)
        except (TypeError, ValueError) as exc:
            raise ClosureRuntimeContractError(
                "ANFIS firing strengths must be finite in [0, 1]"
            ) from exc
        if not math.isfinite(firing) or not 0.0 <= firing <= 1.0:
            raise ClosureRuntimeContractError("ANFIS firing strengths must be finite in [0, 1]")
        firings.append(float(np.float32(firing)))
    if isinstance(missing_fraction, bool):
        raise ClosureRuntimeContractError("ANFIS missing_fraction must be finite in [0, 1]")
    missing = float(missing_fraction)
    if not math.isfinite(missing) or not 0.0 <= missing <= 1.0:
        raise ClosureRuntimeContractError("ANFIS missing_fraction must be finite in [0, 1]")

    firing_sum = math.fsum(firings)
    denominator = max(firing_sum, 1e-12)
    probabilities = [firing / denominator for firing in firings]
    entropy = -math.fsum(
        probability * math.log(min(max(probability, 1e-12), 1.0))
        for probability in probabilities
    )
    if len(probabilities) > 1:
        entropy /= math.log(len(probabilities))
    else:
        entropy = 0.0
    return min(max(0.10 + 0.45 * entropy + 0.35 * missing, 0.0), 1.0)


def anfis_uncertainty_proxy(
    rule_firing_strengths: Sequence[float],
    *,
    module: str,
    missing_fraction: float,
) -> float:
    """Compute a production proxy while enforcing the module's exact rule count."""
    rule_counts = cast(
        Mapping[str, int],
        EXPECTED_ANFIS_UNCERTAINTY_PROXY["rule_count_by_module"],
    )
    try:
        expected_rule_count = rule_counts[module]
    except KeyError as exc:
        raise ClosureRuntimeContractError(
            f"Unregistered primary ANFIS module for uncertainty: {module!r}"
        ) from exc
    return _anfis_uncertainty_proxy(
        rule_firing_strengths,
        expected_rule_count=expected_rule_count,
        missing_fraction=missing_fraction,
    )


def anfis_uncertainty_golden_vector() -> list[float]:
    """Evaluate the short mathematical fixtures that lock proxy normalization."""
    vectors = cast(
        Sequence[Mapping[str, Any]],
        EXPECTED_ANFIS_UNCERTAINTY_PROXY["golden_vectors"],
    )
    return [
        _anfis_uncertainty_proxy(
            cast(Sequence[float], vector["firing_strengths"]),
            expected_rule_count=int(vector["rule_count"]),
            missing_fraction=float(vector["missing_fraction"]),
        )
        for vector in vectors
    ]


def _anfis_hash_rank_sample(
    rows: Sequence[Mapping[str, Any]],
    *,
    module: str,
    module_seed: int,
    selected_rows: int,
    development_keys: AbstractSet[tuple[str, str]] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select keys with the versioned SHA-256 ranking used by Closure ANFIS."""
    if module not in EXPECTED_ANFIS_MODULE_FEATURES:
        raise ClosureRuntimeContractError(f"Unregistered primary ANFIS module: {module!r}")
    if type(module_seed) is not int or module_seed < 0:
        raise ClosureRuntimeContractError("ANFIS module_seed must be a non-negative integer")
    base_seed = module_seed - EXPECTED_MODULE_OFFSETS[module]
    if base_seed not in EXPECTED_SEEDS:
        raise ClosureRuntimeContractError(
            f"ANFIS module_seed {module_seed} is not paired with a locked seed slot for {module}"
        )
    if type(selected_rows) is not int or selected_rows <= 0:
        raise ClosureRuntimeContractError("ANFIS selected_rows must be a positive integer")

    keyed_rows = [(_strict_sample_key(row), row) for row in rows]
    input_keys = [key for key, _ in keyed_rows]
    if len(input_keys) != len(set(input_keys)):
        raise ClosureRuntimeContractError("ANFIS candidate keys must be unique")
    eligible_keys: list[tuple[str, str, str]] = []
    excluded_nonfinite_target_rows = 0
    excluded_missingness_rows = 0
    target_column = EXPECTED_ANFIS_MODULE_TARGETS[module]
    feature_columns = EXPECTED_ANFIS_MODULE_FEATURES[module]
    for key, row in keyed_rows:
        source_id, site_id, year_month = key
        if (
            source_id != "wqp"
            or row.get("assignment_role") != "development"
            or row.get("time_role") != "training"
            or year_month > "2018-12"
        ):
            raise ClosureRuntimeContractError(
                "ANFIS sampler input must contain only WQP development/training rows through 2018-12"
            )
        if development_keys is not None and (source_id, site_id) not in development_keys:
            raise ClosureRuntimeContractError(
                "ANFIS sampler key is absent from the locked E0-C development set"
            )
        target = _optional_finite_float(row.get(target_column))
        if target is None:
            excluded_nonfinite_target_rows += 1
            continue
        if not 0.0 <= target <= 1.0:
            raise ClosureRuntimeContractError(f"ANFIS anchor {target_column!r} must be in [0, 1]")

        missing_features = 0
        for column in feature_columns:
            feature = _optional_finite_float(row.get(column))
            if feature is None:
                missing_features += 1
            elif not 0.0 <= feature <= 1.0:
                raise ClosureRuntimeContractError(f"ANFIS feature {column!r} must be in [0, 1]")
        if missing_features / len(feature_columns) > 0.5:
            excluded_missingness_rows += 1
            continue
        eligible_keys.append(key)

    keys = eligible_keys
    if len(keys) < selected_rows:
        raise ClosureRuntimeContractError(
            f"ANFIS candidate universe has {len(keys)} rows; {selected_rows} are required"
        )

    universe_payloads = sorted(_compact_json_bytes(key) for key in keys)
    universe_digest = hashlib.sha256()
    for payload in universe_payloads:
        universe_digest.update(payload)
        universe_digest.update(b"\n")

    ranked: list[tuple[str, bytes, bytes, str, tuple[str, str, str]]] = []
    for key in keys:
        rank_payload = _compact_json_bytes((int(module_seed), *key))
        rank_sha256 = hashlib.sha256(rank_payload).hexdigest()
        ranked.append((rank_sha256, key[0].encode("utf-8"), key[1].encode("utf-8"), key[2], key))
    ranked.sort()

    selected = ranked[:selected_rows]
    selected_digest = hashlib.sha256()
    records: list[dict[str, Any]] = []
    for rank_sha256, _, _, _, key in selected:
        selected_digest.update(_compact_json_bytes(key))
        selected_digest.update(b"\n")
        records.append(
            {
                "source_id": key[0],
                "site_id": key[1],
                "year_month": key[2],
                "module": module,
                "module_seed": int(module_seed),
                "rank_sha256": rank_sha256,
            }
        )
    audit = {
        "input_rows": len(rows),
        "excluded_nonfinite_target_rows": excluded_nonfinite_target_rows,
        "excluded_missingness_rows": excluded_missingness_rows,
        "eligible_universe_rows": len(keys),
        "eligible_universe_sha256": universe_digest.hexdigest(),
        "selected_rows": len(records),
        "selected_keys_sha256": selected_digest.hexdigest(),
        "module": module,
        "base_seed": base_seed,
        "module_seed": int(module_seed),
    }
    return records, audit


def anfis_hash_rank_sample(
    rows: Sequence[Mapping[str, Any]],
    *,
    module: str,
    module_seed: int,
    development_keys: AbstractSet[tuple[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select the fixed 4,096-row production sample for one Closure ANFIS module."""
    return _anfis_hash_rank_sample(
        rows,
        module=module,
        module_seed=module_seed,
        selected_rows=EXPECTED_ANFIS_CONFIGURATION["train_rows_per_module"],
        development_keys=development_keys,
    )


def anfis_hash_rank_golden_vector() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return the closed NFC/UTF-8 three-candidate sampling test vector."""
    rows = [
        {
            "source_id": "wqp",
            "site_id": site_id,
            "year_month": year_month,
            "assignment_role": "development",
            "time_role": "training",
            "yN": 0.5,
            "tp_pressure": 0.2,
            "tn_pressure": 0.3,
            "ratio_imbalance_pressure": 0.4,
        }
        for site_id, year_month in (("C", "2018-03"), ("\u00c1", "2018-01"), ("B", "2018-02"))
    ]
    return _anfis_hash_rank_sample(
        rows,
        module="ANFIS-N",
        module_seed=1830,
        selected_rows=2,
        development_keys=None,
    )


def _previous_year_month(year_month: str) -> str:
    year, month = (int(part) for part in year_month.split("-"))
    if month == 1:
        return f"{year - 1:04d}-12"
    return f"{year:04d}-{month - 1:02d}"


def _exact_previous_month_deltas(
    rows: Sequence[Mapping[str, Any]],
    *,
    value_columns: Sequence[str],
) -> list[dict[str, Any]]:
    """Compute deltas without substituting an older available observation."""
    if not value_columns:
        raise ClosureRuntimeContractError("At least one state value column is required")
    indexed: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for row in rows:
        key = _strict_sample_key(row)
        if key in indexed:
            raise ClosureRuntimeContractError(f"Duplicate state key for delta calculation: {key!r}")
        for column in value_columns:
            try:
                value = float(row[column])
            except (KeyError, TypeError, ValueError) as exc:
                raise ClosureRuntimeContractError(f"State delta source {column!r} must be numeric") from exc
            if not math.isfinite(value):
                raise ClosureRuntimeContractError(f"State delta source {column!r} must be finite")
        indexed[key] = row

    output: list[dict[str, Any]] = []
    for key in sorted(indexed):
        source_id, site_id, year_month = key
        current = indexed[key]
        previous = indexed.get((source_id, site_id, _previous_year_month(year_month)))
        missing_previous = previous is None
        record: dict[str, Any] = {
            "source_id": source_id,
            "site_id": site_id,
            "year_month": year_month,
            "delta_previous_month_missing": missing_previous,
        }
        for column in value_columns:
            delta_column = f"delta_{column}"
            delta = (
                0.0 if missing_previous else float(current[column]) - float(previous[column])
            )
            if not math.isfinite(delta):
                raise ClosureRuntimeContractError(f"State delta {delta_column!r} must be finite")
            record[delta_column] = delta
        output.append(record)
    return output


def closure_state_deltas(
    model_id: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    development_keys: AbstractSet[tuple[str, str]],
) -> list[dict[str, Any]]:
    """Compute only the three signed no-current Closure deltas for P0 or P1."""
    try:
        value_columns = EXPECTED_DELTA_SOURCE_COLUMNS[model_id]
    except KeyError as exc:
        raise ClosureRuntimeContractError(f"Unsupported Closure temporal model: {model_id!r}") from exc
    for row in rows:
        source_id, site_id, _ = _strict_sample_key(row)
        if (source_id, site_id) not in development_keys:
            raise ClosureRuntimeContractError(
                "Closure state key is absent from the locked E0-C development set"
            )
        for column in value_columns:
            value = _optional_finite_float(row.get(column))
            if value is None or not 0.0 <= value <= 1.0:
                raise ClosureRuntimeContractError(f"Closure state {column!r} must be finite in [0, 1]")
    return _exact_previous_month_deltas(rows, value_columns=value_columns)


def closure_seasonality(calendar_month: int) -> dict[str, float]:
    """Return the exact four Closure seasonal channels for a calendar month."""
    if type(calendar_month) is not int or not 1 <= calendar_month <= 12:
        raise ClosureRuntimeContractError("calendar_month must be an integer in [1, 12]")
    phase = 2.0 * math.pi * (calendar_month - 1) / 12.0
    return {
        "season_sin_annual": math.sin(phase),
        "season_cos_annual": math.cos(phase),
        "season_sin_semiannual": math.sin(2.0 * phase),
        "season_cos_semiannual": math.cos(2.0 * phase),
    }


def rollout_origin_seed(
    base_seed: int,
    *,
    source_id: str,
    site_id: str,
    origin_year_month: str,
) -> int:
    """Derive the batch-order-invariant 128-bit PCG64 seed for one origin."""
    if type(base_seed) is not int or base_seed not in EXPECTED_SEEDS:
        raise ClosureRuntimeContractError(f"Unregistered Closure V1 seed: {base_seed!r}")
    source_id, site_id, origin_year_month = _strict_sample_key(
        {
            "source_id": source_id,
            "site_id": site_id,
            "origin_year_month": origin_year_month,
        },
        month_column="origin_year_month",
    )
    payload = _compact_json_bytes(
        ("closure_v1", base_seed, source_id, site_id, origin_year_month)
    )
    return int.from_bytes(hashlib.sha256(payload).digest()[:16], byteorder="big", signed=False)


def rollout_standard_normal_predraw(
    base_seed: int,
    *,
    source_id: str,
    site_id: str,
    origin_year_month: str,
) -> np.ndarray:
    """Predraw the closed horizon-major float64 PCG64 tensor for one origin."""
    origin_seed = rollout_origin_seed(
        base_seed,
        source_id=source_id,
        site_id=site_id,
        origin_year_month=origin_year_month,
    )
    generator = np.random.Generator(np.random.PCG64(origin_seed))
    return generator.standard_normal((3, 128, 9), dtype=np.float64)


def rollout_predraw_sha256(predraw: np.ndarray) -> str:
    """Hash a closed predraw tensor as little-endian float64 in C order."""
    if predraw.shape != (3, 128, 9):
        raise ClosureRuntimeContractError("Closure rollout predraw must have shape (3, 128, 9)")
    if predraw.dtype != np.float64:
        raise ClosureRuntimeContractError("Closure rollout predraw must use float64")
    if not np.isfinite(predraw).all():
        raise ClosureRuntimeContractError("Closure rollout predraw must be finite")
    serialized = predraw.astype(np.dtype("<f8"), copy=False).tobytes(order="C")
    return hashlib.sha256(serialized).hexdigest()


def closure_rollout_scalar_step(
    *,
    channel: str,
    persistence: float,
    mu: float,
    log_variance: float,
    blend_weight: float,
    epsilon: float,
) -> float:
    """Apply the exact scalar kernel used for each rollout sample and channel."""
    if channel not in EXPECTED_ROLLOUT_STATE_CLIP:
        raise ClosureRuntimeContractError(f"Unknown Closure rollout state channel: {channel!r}")
    values = {
        "persistence": persistence,
        "mu": mu,
        "log_variance": log_variance,
        "blend_weight": blend_weight,
        "epsilon": epsilon,
    }
    numeric: dict[str, float] = {}
    for name, value in values.items():
        if isinstance(value, bool):
            raise ClosureRuntimeContractError(f"Rollout kernel {name} must be finite numeric")
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ClosureRuntimeContractError(f"Rollout kernel {name} must be finite numeric") from exc
        if not math.isfinite(numeric_value):
            raise ClosureRuntimeContractError(f"Rollout kernel {name} must be finite numeric")
        numeric[name] = numeric_value
    float32_max = float(np.finfo(np.float32).max)
    for name in ("persistence", "mu", "log_variance"):
        if abs(numeric[name]) > float32_max:
            raise ClosureRuntimeContractError(
                f"Rollout kernel {name} must be representable as float32"
            )
        numeric[name] = float(np.float32(numeric[name]))
    if not 0.0 <= numeric["blend_weight"] <= 1.0:
        raise ClosureRuntimeContractError("Rollout blend_weight must be in [0, 1]")

    mu_blend = numeric["persistence"] + numeric["blend_weight"] * (
        numeric["mu"] - numeric["persistence"]
    )
    clipped_log_variance = min(max(numeric["log_variance"], -10.0), 2.0)
    sigma = math.exp(0.5 * clipped_log_variance)
    sampled_state = mu_blend + sigma * numeric["epsilon"]
    lower, upper = EXPECTED_ROLLOUT_STATE_CLIP[channel]
    clipped_state = min(max(sampled_state, lower), upper)
    return float(np.float32(clipped_state))


def closure_rollout_recursive_golden_vector() -> list[float]:
    """Return the fixed two-horizon float32-recycled scalar trajectory."""
    vector = cast(Mapping[str, Any], EXPECTED_ROLLOUT_KERNEL["recursive_golden_vector"])
    persistence = float(vector["initial_persistence"])
    output: list[float] = []
    for mu, log_variance, blend_weight, epsilon in zip(
        cast(Sequence[float], vector["mu"]),
        cast(Sequence[float], vector["log_variance"]),
        cast(Sequence[float], vector["blend_weight"]),
        cast(Sequence[float], vector["epsilon"]),
        strict=True,
    ):
        persistence = closure_rollout_scalar_step(
            channel=str(vector["channel"]),
            persistence=persistence,
            mu=mu,
            log_variance=log_variance,
            blend_weight=blend_weight,
            epsilon=epsilon,
        )
        output.append(persistence)
    return output


def render_runtime_artifact_paths(
    runtime: Mapping[str, Any],
    slots: Sequence[Mapping[str, int]],
) -> tuple[list[str], str]:
    """Expand, canonicalize, sort, and hash every planned runtime artifact path."""
    artifacts = _mapping(runtime, "artifacts", context="development_runtime")
    paths: list[str] = []
    for key, raw_template in artifacts.items():
        if not key.endswith("_template"):
            continue
        template = str(raw_template)
        fields = {field for _, field, _, _ in Formatter().parse(template) if field is not None}
        unknown = fields.difference({"base_seed", "module", "model_id"})
        if unknown:
            raise ClosureRuntimeContractError(f"Unknown placeholders in artifacts.{key}: {sorted(unknown)}")
        base_seeds: Sequence[int | None] = (
            [int(slot["base_seed"]) for slot in slots] if "base_seed" in fields else [None]
        )
        modules: Sequence[str | None] = (
            [module.lower().replace("-", "_") for module in EXPECTED_PRIMARY_MODULES]
            if "module" in fields
            else [None]
        )
        model_ids: Sequence[str | None] = ["P0", "P1"] if "model_id" in fields else [None]
        for base_seed in base_seeds:
            for module in modules:
                for model_id in model_ids:
                    paths.append(
                        template.format(base_seed=base_seed, module=module, model_id=model_id)
                    )

    for key, raw_path in artifacts.items():
        if key.endswith("_path") and key not in {"manifest_last"}:
            paths.append(str(raw_path))

    configured_roots = artifacts.get("allowed_output_roots")
    _require_equal(
        tuple(configured_roots) if isinstance(configured_roots, Sequence) else configured_roots,
        ALLOWED_RUNTIME_ARTIFACT_ROOTS,
        context="runtime artifact roots",
    )
    project_root = PROJECT_ROOT.resolve()
    allowed_roots = tuple((project_root / root).resolve(strict=False) for root in ALLOWED_RUNTIME_ARTIFACT_ROOTS)
    canonical_paths: list[str] = []
    resolved_paths: set[Path] = set()
    for path in paths:
        candidate = Path(path)
        canonical = candidate.as_posix()
        if candidate.is_absolute() or canonical != path or ".." in candidate.parts:
            raise ClosureRuntimeContractError(f"Runtime artifact path is not canonical: {path}")
        resolved = (project_root / candidate).resolve(strict=False)
        try:
            resolved.relative_to(project_root)
        except ValueError as exc:
            raise ClosureRuntimeContractError(f"Runtime artifact path is outside the project: {path}") from exc
        if not any(resolved == root or resolved.is_relative_to(root) for root in allowed_roots):
            raise ClosureRuntimeContractError(f"Runtime artifact path uses an unauthorized root: {path}")
        if resolved in resolved_paths:
            raise ClosureRuntimeContractError(
                "Per-seed artifact templates produce colliding canonical output paths"
            )
        resolved_paths.add(resolved)
        canonical_paths.append(canonical)

    canonical_paths.sort(key=lambda value: value.encode("utf-8"))
    digest = hashlib.sha256()
    for path in canonical_paths:
        digest.update(path.encode("utf-8"))
        digest.update(b"\n")
    return canonical_paths, digest.hexdigest()


def _validate_protocol_component_hashes(protocol_lock: Mapping[str, Any]) -> int:
    components = _sequence(protocol_lock, "protocol_components", context="protocol_lock")
    if len(components) != 13:
        raise ClosureRuntimeContractError("Protocol lock must contain exactly 13 protocol components")
    seen: set[str] = set()
    for index, raw_record in enumerate(components):
        if not isinstance(raw_record, Mapping):
            raise ClosureRuntimeContractError(f"protocol_components[{index}] must be a mapping")
        logical_path = raw_record.get("path")
        expected_hash = raw_record.get("sha256")
        expected_bytes = raw_record.get("bytes")
        if not isinstance(logical_path, str) or not isinstance(expected_hash, str):
            raise ClosureRuntimeContractError(f"protocol_components[{index}] lacks path or SHA-256")
        if logical_path in seen:
            raise ClosureRuntimeContractError(f"Duplicate protocol component path: {logical_path}")
        seen.add(logical_path)
        path = resolve_repo_path(logical_path)
        if not path.is_file():
            raise ClosureRuntimeContractError(f"Missing locked protocol component: {logical_path}")
        if path.stat().st_size != int(expected_bytes):
            raise ClosureRuntimeContractError(f"Locked protocol component byte drift: {logical_path}")
        if _sha256_file(path) != expected_hash:
            raise ClosureRuntimeContractError(f"Locked protocol component SHA-256 drift: {logical_path}")
    runtime_paths = {DEFAULT_RUNTIME_CONFIG.as_posix(), DEFAULT_RUNTIME_SCHEMA.as_posix()}
    if seen.intersection(runtime_paths):
        raise ClosureRuntimeContractError("Derived runtime files must not masquerade as sealed E0-P components")
    return len(components)


def _manifest_records_by_path(
    payload: Mapping[str, Any],
    key: str,
    *,
    expected_paths: Sequence[str],
    context: str,
) -> dict[str, Mapping[str, Any]]:
    records = _sequence(payload, key, context=context)
    by_path: dict[str, Mapping[str, Any]] = {}
    for index, raw_record in enumerate(records):
        if not isinstance(raw_record, Mapping):
            raise ClosureRuntimeContractError(f"{context}.{key}[{index}] must be a mapping")
        logical_path = raw_record.get("path")
        if not isinstance(logical_path, str):
            raise ClosureRuntimeContractError(f"{context}.{key}[{index}] lacks a path")
        if logical_path in by_path:
            raise ClosureRuntimeContractError(f"Duplicate {context}.{key} path: {logical_path}")
        by_path[logical_path] = raw_record
    _require_equal(tuple(by_path), tuple(expected_paths), context=f"{context}.{key} paths")
    return by_path


def _validate_physical_manifest_record(
    record: Mapping[str, Any],
    *,
    logical_path: str,
    physical_path: Path | None = None,
    require_present: bool = True,
) -> dict[str, Any]:
    _require_equal(record.get("path"), logical_path, context=f"file record path for {logical_path}")
    expected_bytes = record.get("bytes")
    expected_sha256 = record.get("sha256")
    if type(expected_bytes) is not int or expected_bytes < 0:
        raise ClosureRuntimeContractError(f"File record for {logical_path} has invalid bytes")
    if not isinstance(expected_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
        raise ClosureRuntimeContractError(f"File record for {logical_path} has invalid SHA-256")
    path = physical_path if physical_path is not None else resolve_repo_path(logical_path)
    if not path.is_file():
        if require_present:
            raise ClosureRuntimeContractError(f"Missing common-origin dependency: {logical_path}")
        return {
            "path": logical_path,
            "bytes": expected_bytes,
            "sha256": expected_sha256,
            "present": False,
        }
    _require_equal(path.stat().st_size, expected_bytes, context=f"{logical_path} bytes")
    _require_equal(_sha256_file(path), expected_sha256, context=f"{logical_path} SHA-256")
    return {
        "path": logical_path,
        "bytes": expected_bytes,
        "sha256": expected_sha256,
        "present": True,
    }


def _validate_common_origin_completion(
    *,
    common_origin_path: Path,
    completion_path: Path,
    gate: DevelopmentGate,
    protocol_lock: Mapping[str, Any],
    validate_repository: bool,
) -> dict[str, Any]:
    output_present = common_origin_path.is_file()
    completion_present = completion_path.is_file()
    if output_present and not completion_present:
        raise ClosureRuntimeContractError(
            "The common-origin Parquet exists without its completion manifest"
        )
    if not completion_present:
        return {
            "common_origin_materialized": False,
            "common_origin_completion_manifest_present": False,
            "common_origin_completion_validated": False,
            "common_origin_output_verified": False,
        }

    payload = load_json_mapping(completion_path)
    context = "common_origin_completion"
    _require_equal(
        payload.get("manifest_version"),
        COMMON_ORIGIN_MANIFEST_VERSION,
        context="common-origin manifest version",
    )
    _require_equal(payload.get("status"), "completed", context="common-origin status")
    _require_equal(payload.get("experiment_id"), "closure_v1", context="common-origin experiment")
    _require_equal(
        payload.get("surface_id"),
        "closure_v1_wqp_adaptive_no_current_chla",
        context="common-origin surface",
    )
    sealed_fields = {
        "future_outcomes_accessed": False,
        "target_values_projected": [],
        "target_parquet_semantically_opened": False,
        "post_cutoff_target_rows_materialized": 0,
        "target_availability_used_for_origin_selection": False,
        "availability_join": "left_after_intent_freeze",
    }
    for field, expected in sealed_fields.items():
        _require_typed_equal(payload.get(field), expected, context=f"common-origin {field}")

    execution = _mapping(payload, "execution", context=context)
    repository = _mapping(execution, "repository", context=f"{context}.execution")
    base_head = repository.get("base_head")
    if not isinstance(base_head, str) or re.fullmatch(
        r"(?:[0-9a-f]{40}|[0-9a-f]{64})", base_head
    ) is None:
        raise ClosureRuntimeContractError("common_origin_completion.execution.repository.base_head is invalid")
    _require_typed_equal(
        repository.get("base_head_is_complete_source_identity"),
        False,
        context="common-origin base HEAD identity scope",
    )
    tracked_status = repository.get("tracked_worktree_status")
    tracked_status_lines = repository.get("tracked_status_lines")
    if tracked_status not in {"clean", "dirty"}:
        raise ClosureRuntimeContractError("Common-origin tracked worktree status is invalid")
    if not isinstance(tracked_status_lines, list) or not all(
        isinstance(line, str) and line for line in tracked_status_lines
    ):
        raise ClosureRuntimeContractError("Common-origin tracked status lines are invalid")
    _require_equal(
        tracked_status,
        "dirty" if tracked_status_lines else "clean",
        context="common-origin tracked worktree status",
    )
    _require_equal(
        execution.get("source_tree_identity"),
        "code_config_parent_sha256_records",
        context="common-origin source tree identity",
    )
    if validate_repository:
        ancestry = subprocess.run(
            ["git", "merge-base", "--is-ancestor", base_head, "HEAD"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if ancestry.returncode != 0:
            raise ClosureRuntimeContractError(
                "Common-origin execution base HEAD is not an ancestor of the current HEAD"
            )
    _require_typed_equal(
        execution.get("future_outcomes_semantically_decoded"),
        False,
        context="common-origin execution semantic outcome decode",
    )
    _require_equal(
        execution.get("reproduction_command"),
        [
            "poetry",
            "run",
            "python",
            EXPECTED_COMMON_ORIGIN_CODE_PATHS[0],
            "--panel",
            EXPECTED_COMMON_ORIGIN_SOURCE_PATHS[0],
            "--splits",
            EXPECTED_COMMON_ORIGIN_SOURCE_PATHS[1],
            "--output",
            DEFAULT_COMMON_ORIGIN.as_posix(),
            "--manifest",
            DEFAULT_COMMON_ORIGIN_COMPLETION.as_posix(),
        ],
        context="common-origin reproduction command",
    )

    assignment = _mapping(payload, "assignment", context=context)
    assignment_path = repository_relative(gate.assignment_path)
    _require_equal(assignment.get("path"), assignment_path, context="common-origin assignment path")
    _require_equal(
        assignment.get("sha256"), gate.assignment_sha256, context="common-origin assignment SHA-256"
    )
    _require_equal(
        assignment.get("bytes"), gate.assignment_path.stat().st_size, context="common-origin assignment bytes"
    )
    for key, expected in {
        **gate.expected_counts,
        "holdout_fit_overlap_count": 0,
    }.items():
        _require_equal(assignment.get(key), expected, context=f"common-origin assignment {key}")

    projections = _mapping(payload, "projections", context=context)
    _require_typed_equal(
        dict(projections),
        {
            "panel": list(EXPECTED_COMMON_ORIGIN_PANEL_PROJECTION),
            "target_keys": list(EXPECTED_COMMON_ORIGIN_TARGET_PROJECTION),
            "panel_predicate": (
                "source_id=wqp AND exact development site_id AND year_month<=2021-12"
            ),
            "target_key_predicate": (
                "source_id=wqp AND exact development site_id AND "
                "origin_year_month<=2021-12 AND target_year_month<=2021-12"
            ),
        },
        context="common-origin projections",
    )
    scans = _mapping(payload, "scans", context=context)
    _require_typed_equal(
        dict(scans),
        EXPECTED_COMMON_ORIGIN_SCANS,
        context="common-origin scans",
    )
    for scan_name, expected_scan in EXPECTED_COMMON_ORIGIN_SCANS.items():
        _require_equal(
            expected_scan["materialized_rows"],
            expected_scan["returned_rows"] + expected_scan["boundary_crossing_rows"],
            context=f"common-origin {scan_name} scan conservation",
        )
        _require_equal(
            sum(expected_scan["role_counts"].values()),
            expected_scan["returned_rows"],
            context=f"common-origin {scan_name} role conservation",
        )

    counts = _mapping(payload, "counts", context=context)
    for key, expected in EXPECTED_COMMON_ORIGIN_COUNTS.items():
        _require_typed_equal(counts.get(key), expected, context=f"common-origin counts.{key}")
    _require_typed_equal(
        counts.get("by_role_horizon_target_evaluable"),
        EXPECTED_COMMON_ORIGIN_ROLE_HORIZON_AVAILABILITY,
        context="common-origin counts.by_role_horizon_target_evaluable",
    )
    availability_rows = EXPECTED_COMMON_ORIGIN_ROLE_HORIZON_AVAILABILITY
    _require_equal(
        sum(int(record["rows"]) for record in availability_rows),
        EXPECTED_COMMON_ORIGIN_COUNTS["rows"],
        context="common-origin availability row conservation",
    )
    _require_equal(
        sum(int(record["rows"]) for record in availability_rows if record["target_evaluable"]),
        EXPECTED_COMMON_ORIGIN_COUNTS["target_evaluable_rows"],
        context="common-origin target-evaluable row conservation",
    )
    for role, expected_origins in EXPECTED_COMMON_ORIGIN_COUNTS["intent_origins_by_role"].items():
        for horizon in (1, 2, 3):
            role_horizon_rows = sum(
                int(record["rows"])
                for record in availability_rows
                if record["time_role"] == role and record["horizon_months"] == horizon
            )
            _require_equal(
                role_horizon_rows,
                expected_origins,
                context=f"common-origin {role} h{horizon} row conservation",
            )
    intent_audit = _mapping(payload, "intent_origin_audit", context=context)
    expected_intent_audit = {
        "monthly_status_rows": 42110,
        "input_eligible_month_rows": 34589,
        "history_candidate_origins": 10081,
        "retained_intent_origins": 9732,
        "excluded_role_crossing_origins": 238,
        "excluded_locked_evaluation_origins": 111,
    }
    _require_exact_mapping(intent_audit, expected_intent_audit, context="common-origin intent audit")
    invariants = _mapping(payload, "invariants", context=context)
    _require_exact_mapping(
        invariants,
        {
            "holdout_overlap_count": 0,
            "unknown_assignment_count": 0,
            "post_2021_materialized_count": 0,
            "chlorophyll_columns_projected": 0,
            "duplicate_exact_keys": 0,
            "rows_per_origin": 3,
            "target_arithmetic_exact": True,
            "one_role_per_origin": True,
            "history_length_months": 12,
            "horizons_months": [1, 2, 3],
        },
        context="common-origin invariants",
    )

    source_records = _manifest_records_by_path(
        payload,
        "source_inputs",
        expected_paths=EXPECTED_COMMON_ORIGIN_SOURCE_PATHS,
        context=context,
    )
    for logical_path, record in source_records.items():
        source_bytes = record.get("bytes")
        source_sha256 = record.get("sha256")
        if type(source_bytes) is not int or source_bytes < 0:
            raise ClosureRuntimeContractError(
                f"Common-origin source {logical_path} has invalid bytes"
            )
        if not isinstance(source_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", source_sha256) is None:
            raise ClosureRuntimeContractError(
                f"Common-origin source {logical_path} has invalid SHA-256"
            )
        if record.get("hash_source") != "protocol_lock":
            raise ClosureRuntimeContractError(
                f"Common-origin source {logical_path} is not anchored to the protocol lock"
            )
        locked = _locked_source_artifact(
            protocol_lock,
            logical_path=logical_path,
            expected_sha256=source_sha256,
        )
        _require_equal(source_bytes, locked.get("bytes"), context=f"{logical_path} locked bytes")
        _require_equal(record.get("role"), locked.get("role"), context=f"{logical_path} locked role")

    for section, expected_paths in (
        ("code", EXPECTED_COMMON_ORIGIN_CODE_PATHS),
        ("configs", EXPECTED_COMMON_ORIGIN_CONFIG_PATHS),
    ):
        records = _manifest_records_by_path(
            payload,
            section,
            expected_paths=expected_paths,
            context=context,
        )
        for logical_path, record in records.items():
            _validate_physical_manifest_record(record, logical_path=logical_path)

    parent_records = _sequence(payload, "parent_artifacts", context=context)
    expected_parents = (
        ("protocol_lock", gate.protocol_lock_path, gate.protocol_lock_sha256),
        ("holdout_manifest", gate.holdout_manifest_path, gate.holdout_manifest_sha256),
        ("holdout_assignment", gate.assignment_path, gate.assignment_sha256),
    )
    if len(parent_records) != len(expected_parents):
        raise ClosureRuntimeContractError("Common-origin completion must list exactly three parent artifacts")
    for index, (raw_record, (role, path, expected_sha256)) in enumerate(
        zip(parent_records, expected_parents, strict=True)
    ):
        if not isinstance(raw_record, Mapping):
            raise ClosureRuntimeContractError(f"common-origin parent_artifacts[{index}] must be a mapping")
        _require_equal(raw_record.get("role"), role, context=f"common-origin parent role {index}")
        observed = _validate_physical_manifest_record(
            raw_record,
            logical_path=repository_relative(path),
            physical_path=path,
        )
        _require_equal(observed["sha256"], expected_sha256, context=f"common-origin parent {role} SHA-256")

    output_record = _mapping(payload, "output", context=context)
    output_audit = _validate_physical_manifest_record(
        output_record,
        logical_path=DEFAULT_COMMON_ORIGIN.as_posix(),
        physical_path=common_origin_path,
        require_present=False,
    )
    return {
        "common_origin_materialized": bool(output_audit["present"]),
        "common_origin_completion_manifest_present": True,
        "common_origin_completion_validated": True,
        "common_origin_output_verified": bool(output_audit["present"]),
        "common_origin_output_sha256": output_audit["sha256"],
        "common_origin_completion_sha256": _sha256_file(completion_path),
        "common_origin_intent_origins": EXPECTED_COMMON_ORIGIN_COUNTS["intent_origins"],
        "common_origin_rows": EXPECTED_COMMON_ORIGIN_COUNTS["rows"],
    }


def _validate_promoted_anfis_reference(runtime: Mapping[str, Any]) -> dict[str, Any]:
    anfis = _mapping(runtime, "anfis", context="development_runtime")
    reference_path = resolve_repo_path(str(anfis["configuration_reference"]))
    expected_hash = str(anfis["configuration_reference_sha256"])
    _require_equal(expected_hash, EXPECTED_ANFIS_REFERENCE_SHA256, context="ANFIS reference SHA-256")
    observed_hash = _sha256_file(reference_path)
    _require_equal(observed_hash, expected_hash, context="promoted ANFIS reference SHA-256")
    return {
        "path": repository_relative(reference_path),
        "bytes": reference_path.stat().st_size,
        "sha256": observed_hash,
        "semantic_decode": False,
    }


def _validate_promoted_pipe_reference(runtime: Mapping[str, Any]) -> dict[str, Any]:
    temporal = _mapping(runtime, "temporal_models", context="development_runtime")
    reference_path = resolve_repo_path(str(temporal["configuration_reference"]))
    expected_hash = str(temporal["configuration_reference_sha256"])
    _require_equal(expected_hash, EXPECTED_PIPE_REFERENCE_SHA256, context="PIPE reference SHA-256")
    observed_hash = _sha256_file(reference_path)
    _require_equal(observed_hash, expected_hash, context="promoted PIPE reference SHA-256")
    return {
        "path": repository_relative(reference_path),
        "bytes": reference_path.stat().st_size,
        "sha256": observed_hash,
        "semantic_decode": False,
    }


def _locked_source_artifact(
    protocol_lock: Mapping[str, Any],
    *,
    logical_path: str,
    expected_sha256: str,
) -> Mapping[str, Any]:
    sources = _sequence(protocol_lock, "source_artifacts", context="protocol_lock")
    matches = [record for record in sources if isinstance(record, Mapping) and record.get("path") == logical_path]
    if len(matches) != 1:
        raise ClosureRuntimeContractError(f"Expected one locked source artifact for {logical_path}")
    record = cast(Mapping[str, Any], matches[0])
    _require_equal(record.get("sha256"), expected_sha256, context=f"locked source {logical_path} SHA-256")
    return record


def _validate_target_artifact_records(
    runtime: Mapping[str, Any],
    protocol_lock: Mapping[str, Any],
) -> dict[str, Any]:
    outcomes = _mapping(runtime, "scientific_outcomes", context="development_runtime")
    target_path = str(outcomes["target_artifact_path"])
    target_hash = str(outcomes["target_artifact_sha256"])
    manifest_path_value = str(outcomes["target_manifest_path"])
    manifest_hash = str(outcomes["target_manifest_sha256"])
    _require_equal(target_hash, EXPECTED_TARGET_ARTIFACT_SHA256, context="target artifact SHA-256")
    _require_equal(manifest_hash, EXPECTED_TARGET_MANIFEST_SHA256, context="target manifest SHA-256")
    _locked_source_artifact(protocol_lock, logical_path=target_path, expected_sha256=target_hash)
    locked_manifest = _locked_source_artifact(
        protocol_lock,
        logical_path=manifest_path_value,
        expected_sha256=manifest_hash,
    )

    return {
        "path": manifest_path_value,
        "bytes": int(locked_manifest["bytes"]),
        "sha256": manifest_hash,
        "semantic_decode": False,
    }


def _cross_validate_locked_contract(
    runtime: Mapping[str, Any],
    *,
    validate_repository: bool,
    require_restored_development_sources: bool,
) -> dict[str, Any]:
    authority = _mapping(runtime, "authority", context="development_runtime")
    parent_hashes = {
        "protocol_lock_sha256": (
            "protocol_lock_path",
            EXPECTED_PROTOCOL_LOCK_SHA256,
        ),
        "holdout_assignment_sha256": (
            "holdout_assignment_path",
            EXPECTED_HOLDOUT_ASSIGNMENT_SHA256,
        ),
        "holdout_manifest_sha256": (
            "holdout_manifest_path",
            EXPECTED_HOLDOUT_MANIFEST_SHA256,
        ),
    }
    for hash_field, (path_field, expected_hash) in parent_hashes.items():
        _require_equal(authority[hash_field], expected_hash, context=f"authority.{hash_field}")
        observed_hash = _sha256_file(resolve_repo_path(str(authority[path_field])))
        _require_equal(observed_hash, expected_hash, context=f"authority.{path_field} SHA-256")
    analysis_plan, _ = load_and_validate_analysis_plan(
        str(authority["analysis_plan_path"]),
        require_files=True,
        reject_unresolved=True,
    )
    gate = load_development_gate(
        assignment_path=str(authority["holdout_assignment_path"]),
        manifest_path=str(authority["holdout_manifest_path"]),
        protocol_lock_path=str(authority["protocol_lock_path"]),
        analysis_plan_path=str(authority["analysis_plan_path"]),
        validate_repository=validate_repository,
    )
    protocol_lock = load_json_mapping(str(authority["protocol_lock_path"]))
    component_count = _validate_protocol_component_hashes(protocol_lock)

    primary_surface = load_yaml_mapping(str(authority["primary_surface_path"]))
    model_benchmark = load_yaml_mapping(str(authority["model_benchmark_path"]))
    seeds = _mapping(runtime, "seeds", context="development_runtime")
    slots = validate_seed_slots(_sequence(seeds, "ordered_slots", context="development_runtime.seeds"))
    locked_plan_seeds = tuple(
        int(value)
        for value in _sequence(
            _mapping(analysis_plan, "seeds", context="analysis_plan"),
            "values",
            context="analysis_plan.seeds",
        )
    )
    _require_equal(locked_plan_seeds, EXPECTED_SEEDS, context="analysis_plan seeds")
    _require_equal(
        tuple(int(value) for value in _sequence(model_benchmark, "seeds", context="model_benchmark")),
        EXPECTED_SEEDS,
        context="model_benchmark seeds",
    )

    scope = _mapping(runtime, "development_scope", context="development_runtime")
    roles = _mapping(analysis_plan, "time_roles", context="analysis_plan")
    training = _mapping(roles, "training", context="analysis_plan.time_roles")
    selection = _mapping(roles, "model_selection", context="analysis_plan.time_roles")
    calibration = _mapping(roles, "calibration_threshold", context="analysis_plan.time_roles")
    evaluation = _mapping(roles, "locked_evaluation", context="analysis_plan.time_roles")
    _require_equal(scope["fit_target_end"], training["target_end"], context="training target boundary")
    _require_equal(scope["model_selection_start"], selection["origin_start"], context="selection start")
    _require_equal(scope["model_selection_end"], selection["target_end"], context="selection end")
    _require_equal(
        scope["calibration_threshold_start"],
        calibration["origin_start"],
        context="calibration start",
    )
    _require_equal(
        scope["calibration_threshold_end"],
        calibration["target_end"],
        context="calibration end",
    )
    _require_equal(scope["locked_evaluation_start"], evaluation["target_start"], context="evaluation start")

    state = _mapping(runtime, "primary_autoregressive_state", context="development_runtime")
    model_state_mappings = _mapping(
        state,
        "model_state_mappings",
        context="primary_autoregressive_state",
    )
    validated_mappings: dict[str, dict[str, str]] = {}
    for model_id in ("P0", "P1"):
        model_mapping = _mapping(model_state_mappings, model_id, context="model_state_mappings")
        input_mapping = validate_autoregressive_state_mapping(
            model_id,
            _mapping(model_mapping, "input_state_mapping", context=f"model_state_mappings.{model_id}"),
        )
        target_mapping = validate_autoregressive_state_mapping(
            model_id,
            _mapping(model_mapping, "target_state_mapping", context=f"model_state_mappings.{model_id}"),
        )
        _require_equal(target_mapping, input_mapping, context=f"{model_id} input/target state mapping")
        _require_exact_mapping(
            _mapping(
                model_mapping,
                "target_to_next_input_mapping",
                context=f"model_state_mappings.{model_id}",
            ),
            EXPECTED_TARGET_TO_NEXT_INPUT_MAPPING,
            context=f"{model_id} target-to-next-input mapping",
        )
        validated_mappings[model_id] = input_mapping
    p0_mapping = validated_mappings["P0"]
    p1_mapping = validated_mappings["P1"]
    _require_equal(tuple(state["input_columns"]), EXPECTED_INPUT_COLUMNS, context="runtime input columns")
    _require_equal(tuple(state["target_columns"]), EXPECTED_TARGET_COLUMNS, context="runtime target columns")
    _require_equal(state["optional_context_columns"], [], context="runtime optional context columns")
    _require_exact_mapping(
        _mapping(state, "sequence_table", context="primary_autoregressive_state"),
        EXPECTED_SEQUENCE_TABLE,
        context="Closure sequence physical schema",
    )
    _require_exact_mapping(
        _mapping(state, "seasonality", context="primary_autoregressive_state"),
        EXPECTED_SEASONALITY,
        context="Closure seasonality",
    )

    surface_mapping = _mapping(primary_surface, "state_lineage_mapping", context="surface_primary")
    expected_surface_mapping = {f"x_{channel}": source for channel, source in p1_mapping.items()}
    _require_exact_mapping(surface_mapping, expected_surface_mapping, context="surface_primary.state_lineage_mapping")
    permitted = _mapping(primary_surface, "permitted_pipe_sequence_channels", context="surface_primary")
    locked_input_columns = tuple(
        [str(value) for value in permitted["state"]]
        + [str(value) for value in permitted["uncertainty"]]
        + [str(value) for value in permitted["change"]]
        + [str(value) for value in permitted["seasonality"]]
    )
    _require_equal(locked_input_columns, EXPECTED_INPUT_COLUMNS, context="surface primary input allowlist")

    models = _mapping(model_benchmark, "models", context="model_benchmark")
    f1 = _mapping(models, "F1", context="model_benchmark.models")
    _require_equal(tuple(f1["modules"]), LOCKED_F1_MODULE_NAMES, context="locked F1 modules")
    p0 = _mapping(models, "P0", context="model_benchmark.models")
    p1 = _mapping(models, "P1", context="model_benchmark.models")
    _require_equal(p0["input_surface"], "no_current_chla", context="locked P0 input surface")
    _require_equal(p1["input_surface"], "adaptive_no_current_chla", context="locked P1 input surface")
    for model_id, locked_model in (("P0", p0), ("P1", p1)):
        _require_exact_mapping(
            _mapping(locked_model, "architecture", context=f"model_benchmark.models.{model_id}"),
            EXPECTED_LOCKED_PIPE_ARCHITECTURE,
            context=f"locked {model_id} architecture",
        )
        _require_equal(
            locked_model["rollout_samples_per_origin"],
            128,
            context=f"locked {model_id} rollout samples",
        )

    anfis = _mapping(runtime, "anfis", context="development_runtime")
    _require_equal(tuple(anfis["primary_modules"]), EXPECTED_PRIMARY_MODULES, context="primary ANFIS modules")
    _require_exact_mapping(
        _mapping(anfis, "module_seed_offsets", context="development_runtime.anfis"),
        EXPECTED_MODULE_OFFSETS,
        context="ANFIS module offsets",
    )
    _require_exact_mapping(
        _mapping(anfis, "fixed_configuration", context="development_runtime.anfis"),
        EXPECTED_ANFIS_CONFIGURATION,
        context="fixed ANFIS configuration",
    )
    _require_exact_mapping(
        _mapping(anfis, "model_initialization", context="development_runtime.anfis"),
        EXPECTED_ANFIS_INITIALIZATION,
        context="ANFIS model initialization",
    )
    _require_exact_mapping(
        _mapping(anfis, "uncertainty_proxy", context="development_runtime.anfis"),
        EXPECTED_ANFIS_UNCERTAINTY_PROXY,
        context="ANFIS uncertainty proxy",
    )
    for observed_sigma, vector in zip(
        anfis_uncertainty_golden_vector(),
        cast(
            Sequence[Mapping[str, Any]],
            EXPECTED_ANFIS_UNCERTAINTY_PROXY["golden_vectors"],
        ),
        strict=True,
    ):
        if not math.isclose(
            observed_sigma,
            float(vector["sigma"]),
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            raise ClosureRuntimeContractError("ANFIS uncertainty golden vector drifted")
    _require_exact_mapping(
        _mapping(anfis, "sampling", context="development_runtime.anfis"),
        EXPECTED_ANFIS_SAMPLING,
        context="ANFIS hash-ranked sampling",
    )
    source_projection = _mapping(anfis, "source_projection", context="development_runtime.anfis")
    _locked_source_artifact(
        protocol_lock,
        logical_path=str(source_projection["panel_path"]),
        expected_sha256=EXPECTED_PANEL_SHA256,
    )
    _require_equal(
        source_projection["expert_anchor_sha256"],
        EXPECTED_EXPERT_STATE_SHA256,
        context="ANFIS expert anchor SHA-256",
    )
    if require_restored_development_sources:
        _require_equal(
            _sha256_file(resolve_repo_path(str(source_projection["panel_path"]))),
            EXPECTED_PANEL_SHA256,
            context="ANFIS panel file SHA-256",
        )
        _require_equal(
            _sha256_file(resolve_repo_path(str(source_projection["expert_anchor_path"]))),
            EXPECTED_EXPERT_STATE_SHA256,
            context="ANFIS expert anchor file SHA-256",
        )
    validate_anfis_raw_projection_columns(
        cast(Sequence[str], source_projection["panel_columns"]),
        cast(Sequence[str], source_projection["expert_anchor_columns"]),
    )
    _require_exact_mapping(
        _mapping(source_projection, "panel_anchor_join", context="anfis.source_projection"),
        EXPECTED_ANFIS_PANEL_ANCHOR_JOIN,
        context="ANFIS panel-anchor join",
    )
    _require_exact_mapping(
        _mapping(source_projection, "derived_feature_lineage", context="anfis.source_projection"),
        EXPECTED_ANFIS_FEATURE_LINEAGE,
        context="ANFIS derived feature lineage",
    )
    _require_exact_mapping(
        _mapping(
            source_projection,
            "derived_feature_transformations",
            context="anfis.source_projection",
        ),
        EXPECTED_ANFIS_FEATURE_TRANSFORMATIONS,
        context="ANFIS derived feature transformations",
    )
    _require_equal(
        tuple(source_projection["forbidden_exact_columns"]),
        tuple(primary_surface["forbidden_predictors"]),
        context="ANFIS forbidden source projection",
    )
    _require_equal(
        tuple(source_projection["forbidden_lineage_patterns"]),
        tuple(primary_surface["forbidden_lineage_patterns"]),
        context="ANFIS forbidden lineage patterns",
    )
    state_export = _mapping(state, "state_export", context="primary_autoregressive_state")
    _require_equal(
        source_projection["expert_anchor_path"],
        state_export["p0_source_path"],
        context="ANFIS expert anchor source path",
    )
    _require_equal(anfis["sampling_seed_equals_optimization_seed"], True, context="ANFIS seed reuse")
    _require_equal(anfis["seed_set_before_model_construction"], True, context="ANFIS model-construction seed")
    for slot in slots:
        anfis_module_substreams(slot["base_seed"])

    temporal = _mapping(runtime, "temporal_models", context="development_runtime")
    _require_exact_mapping(
        _mapping(temporal, "common_architecture", context="development_runtime.temporal_models"),
        EXPECTED_TEMPORAL_ARCHITECTURE,
        context="Closure temporal architecture",
    )
    temporal_inputs = _mapping(temporal, "model_inputs", context="development_runtime.temporal_models")
    _require_equal(
        _mapping(temporal_inputs, "P0", context="temporal_models.model_inputs")["input_surface"],
        p0["input_surface"],
        context="P0 runtime input surface",
    )
    _require_equal(
        _mapping(temporal_inputs, "P1", context="temporal_models.model_inputs")["input_surface"],
        p1["input_surface"],
        context="P1 runtime input surface",
    )
    _require_equal(
        _mapping(temporal, "optimization", context="development_runtime.temporal_models")[
            "early_stopping_patience_epochs"
        ],
        EXPECTED_LOCKED_PIPE_ARCHITECTURE["early_stopping_patience_epochs"],
        context="Closure temporal early stopping patience",
    )
    training_randomness = _mapping(
        temporal,
        "training_randomness",
        context="development_runtime.temporal_models",
    )
    dataloader = _mapping(
        training_randomness,
        "dataloader",
        context="temporal_models.training_randomness",
    )
    for field, expected in EXPECTED_TRAINING_DEVICE_POLICY.items():
        _require_equal(
            training_randomness[field],
            expected,
            context=f"Closure training device policy.{field}",
        )
    _require_exact_mapping(
        _mapping(dataloader, "batch_order_digest", context="temporal_models.dataloader"),
        EXPECTED_BATCH_ORDER_DIGEST,
        context="Closure epoch batch-order digest",
    )
    checkpoint_selection = _mapping(
        temporal,
        "checkpoint_selection",
        context="development_runtime.temporal_models",
    )
    _require_exact_mapping(
        _mapping(
            checkpoint_selection,
            "artifact_lifecycle",
            context="temporal_models.checkpoint_selection",
        ),
        EXPECTED_CHECKPOINT_ARTIFACT_LIFECYCLE,
        context="Closure checkpoint artifact lifecycle",
    )
    rollout = _mapping(temporal, "rollout", context="development_runtime.temporal_models")
    _require_equal(
        rollout["samples_per_origin"],
        128,
        context="Closure runtime rollout samples",
    )
    _require_exact_mapping(
        _mapping(rollout, "rng", context="temporal_models.rollout"),
        EXPECTED_ROLLOUT_RNG,
        context="Closure rollout RNG",
    )
    _require_exact_mapping(
        _mapping(rollout, "state_clip_by_channel", context="temporal_models.rollout"),
        EXPECTED_ROLLOUT_STATE_CLIP,
        context="Closure rollout state clipping",
    )
    _require_exact_mapping(
        _mapping(rollout, "kernel", context="temporal_models.rollout"),
        EXPECTED_ROLLOUT_KERNEL,
        context="Closure rollout kernel",
    )
    _require_exact_mapping(
        _mapping(rollout, "output_table", context="temporal_models.rollout"),
        EXPECTED_ROLLOUT_OUTPUT_TABLE,
        context="Closure rollout physical schema",
    )
    _require_exact_mapping(
        _mapping(rollout, "calibration_raw_score", context="temporal_models.rollout"),
        EXPECTED_CALIBRATION_RAW_SCORE,
        context="Closure calibration raw score",
    )
    golden_predraw = cast(Mapping[str, Any], EXPECTED_ROLLOUT_RNG["golden_predraw"])
    observed_predraw_sha256 = rollout_predraw_sha256(
        rollout_standard_normal_predraw(
            int(golden_predraw["base_seed"]),
            source_id=str(golden_predraw["source_id"]),
            site_id=str(golden_predraw["site_id"]),
            origin_year_month=str(golden_predraw["origin_year_month"]),
        )
    )
    _require_equal(
        observed_predraw_sha256,
        golden_predraw["sha256"],
        context="Closure rollout PCG64 predraw golden digest",
    )
    recursive_golden = cast(
        Mapping[str, Any],
        EXPECTED_ROLLOUT_KERNEL["recursive_golden_vector"],
    )
    _require_equal(
        closure_rollout_recursive_golden_vector(),
        recursive_golden["recycled_float32_states"],
        context="Closure rollout recursive float32 golden vector",
    )

    artifacts = _mapping(runtime, "artifacts", context="development_runtime")
    path_resolution = _mapping(artifacts, "logical_path_resolution", context="development_runtime.artifacts")
    _require_equal(
        path_resolution["locked_adaptive_state_path"],
        primary_surface["state_path"],
        context="logical adaptive state path",
    )
    _require_equal(
        path_resolution["concrete_adaptive_state_template"],
        artifacts["anfis_state_template"],
        context="concrete adaptive state template",
    )
    _require_equal(
        path_resolution["locked_adaptive_sequence_path"],
        primary_surface["sequence_path"],
        context="logical adaptive sequence path",
    )
    _require_equal(
        path_resolution["concrete_adaptive_sequence_template"],
        artifacts["adaptive_sequence_template"],
        context="concrete adaptive sequence template",
    )
    rendered_paths, rendered_paths_sha256 = render_runtime_artifact_paths(runtime, slots)
    _require_equal(
        artifacts["planned_concrete_path_count"],
        EXPECTED_PLANNED_ARTIFACT_PATH_COUNT,
        context="planned runtime artifact count",
    )
    _require_equal(
        len(rendered_paths),
        EXPECTED_PLANNED_ARTIFACT_PATH_COUNT,
        context="rendered runtime artifact count",
    )
    _require_equal(
        artifacts["planned_concrete_paths_sha256"],
        EXPECTED_PLANNED_ARTIFACT_PATHS_SHA256,
        context="declared runtime artifact path digest",
    )
    _require_equal(
        rendered_paths_sha256,
        EXPECTED_PLANNED_ARTIFACT_PATHS_SHA256,
        context="planned runtime artifact path digest",
    )

    implementation_lock = _mapping(
        runtime,
        "implementation_lock",
        context="development_runtime",
    )
    _require_equal(
        implementation_lock["contract_publication_state"],
        "common_origin_published_adapters_ready_pending_expert_state_and_e0_dl",
        context="implementation lock publication state",
    )
    _require_equal(
        tuple(implementation_lock["required_component_roles"]),
        EXPECTED_RUNTIME_COMPONENT_ROLES,
        context="implementation lock component roles",
    )
    _require_exact_mapping(
        _mapping(
            implementation_lock,
            "required_component_paths",
            context="development_runtime.implementation_lock",
        ),
        EXPECTED_RUNTIME_COMPONENT_PATHS,
        context="implementation lock component paths",
    )
    _require_equal(
        tuple(implementation_lock["required_parent_hashes"]),
        EXPECTED_RUNTIME_PARENT_HASH_ROLES,
        context="implementation lock parent hash roles",
    )
    _require_exact_mapping(
        _mapping(
            implementation_lock,
            "required_parent_paths",
            context="development_runtime.implementation_lock",
        ),
        EXPECTED_RUNTIME_PARENT_PATHS,
        context="implementation lock parent paths",
    )
    _require_equal(
        tuple(implementation_lock["required_legacy_dependency_paths"]),
        EXPECTED_RUNTIME_LEGACY_DEPENDENCY_PATHS,
        context="implementation lock legacy dependency paths",
    )
    _require_exact_mapping(
        _mapping(
            implementation_lock,
            "required_authorization_fields",
            context="development_runtime.implementation_lock",
        ),
        EXPECTED_RUNTIME_AUTHORIZATION,
        context="implementation lock authorization",
    )
    _require_exact_mapping(
        _mapping(
            implementation_lock,
            "canonical_origin_identity",
            context="development_runtime.implementation_lock",
        ),
        EXPECTED_RUNTIME_CANONICAL_ORIGIN_IDENTITY,
        context="implementation lock canonical origin identity",
    )
    _require_equal(
        implementation_lock["dvc_remote_name"],
        "gcsremote",
        context="implementation lock DVC remote name",
    )
    _require_equal(
        implementation_lock["dvc_remote_verification_method"],
        "two_targeted_idempotent_pushes_v1",
        context="implementation lock DVC verification method",
    )

    outcomes = _mapping(runtime, "scientific_outcomes", context="development_runtime")
    _require_exact_mapping(
        _mapping(outcomes, "source_columns", context="development_runtime.scientific_outcomes"),
        EXPECTED_OUTCOME_SOURCES,
        context="scientific outcome sources",
    )
    _require_exact_mapping(
        _mapping(outcomes, "frozen_target_policy", context="development_runtime.scientific_outcomes"),
        {
            "horizons_months": [1, 2, 3],
            "bloom_threshold_chla_ugL": 30.0,
            "risk_policy": {"epsilon": 0.1, "low_chla_ugL": 5.0, "bloom_chla_ugL": 30.0},
            "trophic_state_proxy": {
                "oligotrophic_max": 2.6,
                "mesotrophic_max": 7.3,
                "eutrophic_max": 56.0,
            },
        },
        context="frozen target policy",
    )
    if set(p0_mapping.values()).intersection(EXPECTED_OUTCOME_SOURCES.values()) or set(
        p1_mapping.values()
    ).intersection(EXPECTED_OUTCOME_SOURCES.values()):
        raise ClosureRuntimeContractError("Scientific outcomes cannot enter the autoregressive state mapping")

    promoted_reference = _validate_promoted_anfis_reference(runtime)
    promoted_pipe_reference = _validate_promoted_pipe_reference(runtime)
    target_artifact_records = _validate_target_artifact_records(runtime, protocol_lock)
    common_origin_path = resolve_repo_path(str(authority["common_origin_manifest_path"]))
    common_origin_completion_path = resolve_repo_path(
        str(authority["common_origin_completion_manifest_path"])
    )
    common_origin_summary = _validate_common_origin_completion(
        common_origin_path=common_origin_path,
        completion_path=common_origin_completion_path,
        gate=gate,
        protocol_lock=protocol_lock,
        validate_repository=validate_repository,
    )
    return {
        "protocol_component_count": component_count,
        "locked_repository_head": gate.locked_repository_head,
        "assignment_sha256": gate.assignment_sha256,
        "development_location_count": len(gate.development_keys),
        "holdout_location_count": len(gate.holdout_keys),
        "seed_count": len(slots),
        "rendered_seed_artifact_count": len(rendered_paths),
        "planned_artifact_paths_sha256": rendered_paths_sha256,
        "rollout_predraw_golden_sha256": observed_predraw_sha256,
        "promoted_anfis_reference": promoted_reference,
        "promoted_pipe_reference": promoted_pipe_reference,
        "target_artifact_records": target_artifact_records,
        **common_origin_summary,
        "restored_development_sources_verified": require_restored_development_sources,
        "restored_development_source_paths_verified": (
            [source_projection["panel_path"], source_projection["expert_anchor_path"]]
            if require_restored_development_sources
            else []
        ),
    }


def validate_development_runtime(
    runtime: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    cross_validate_locked: bool = True,
    validate_repository: bool = True,
    require_restored_development_sources: bool = False,
) -> dict[str, Any]:
    """Validate the closed runtime payload and, by default, its locked parents."""
    authoritative_schema = load_json_mapping(DEFAULT_RUNTIME_SCHEMA)
    _require_typed_equal(
        dict(schema),
        authoritative_schema,
        context="authoritative Closure runtime schema",
    )
    try:
        validate_json_schema(runtime, schema, instance_path="$.development_runtime")
    except ClosureContractError as exc:
        raise ClosureRuntimeContractError(str(exc)) from exc
    properties = _mapping(authoritative_schema, "properties", context="runtime_schema")
    expected_runtime = {
        key: _mapping(properties, key, context="runtime_schema.properties")["const"]
        for key in properties
    }
    _require_typed_equal(
        dict(runtime),
        expected_runtime,
        context="typed Closure runtime contract",
    )
    _require_equal(runtime.get("schema_version"), RUNTIME_SCHEMA_VERSION, context="runtime schema version")
    if not cross_validate_locked:
        return {"schema_version": RUNTIME_SCHEMA_VERSION, "cross_validated_locked_contract": False}
    summary = _cross_validate_locked_contract(
        runtime,
        validate_repository=validate_repository,
        require_restored_development_sources=require_restored_development_sources,
    )
    return {
        "schema_version": RUNTIME_SCHEMA_VERSION,
        "cross_validated_locked_contract": True,
        **summary,
    }


def load_and_validate_development_runtime(
    config_path: str | Path = DEFAULT_RUNTIME_CONFIG,
    schema_path: str | Path = DEFAULT_RUNTIME_SCHEMA,
    *,
    cross_validate_locked: bool = True,
    validate_repository: bool = True,
    require_restored_development_sources: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load the public runtime config and return it with an audit summary."""
    runtime = load_yaml_mapping(config_path)
    schema = load_json_mapping(schema_path)
    summary = validate_development_runtime(
        runtime,
        schema,
        cross_validate_locked=cross_validate_locked,
        validate_repository=validate_repository,
        require_restored_development_sources=require_restored_development_sources,
    )
    config_resolved = resolve_repo_path(config_path)
    schema_resolved = resolve_repo_path(schema_path)
    implementation_lock = _mapping(runtime, "implementation_lock", context="development_runtime")
    implementation_lock_path = resolve_repo_path(str(implementation_lock["lock_manifest_path"]))
    authority = _mapping(runtime, "authority", context="development_runtime")
    implementation_lock_present = implementation_lock_path.is_file()
    implementation_lock_summary: dict[str, Any] | None = None
    if implementation_lock_present:
        # Local import avoids a cycle: the external-lock validator imports this
        # module lazily only when it expands the closed artifact path plan.
        from src.experiments.closure_development_runtime_lock import (
            load_and_validate_development_runtime_lock,
        )

        _, implementation_lock_summary = load_and_validate_development_runtime_lock(
            Path(str(implementation_lock["lock_manifest_path"])),
            Path(str(implementation_lock["lock_schema_path"])),
            runtime_config=Path(config_path),
            runtime_schema=Path(schema_path),
            require_published=validate_repository,
            require_physical_artifacts=False,
        )
    fit_authorized = bool(
        implementation_lock_summary is not None
        and implementation_lock_summary.get("fit_authorized") is True
    )
    summary.update(
        {
            "config_path": repository_relative(config_resolved),
            "config_sha256": _sha256_file(config_resolved),
            "schema_path": repository_relative(schema_resolved),
            "schema_sha256": _sha256_file(schema_resolved),
            "status": runtime["status"],
            "implementation_lock_present": implementation_lock_present,
            "implementation_lock_validated": implementation_lock_summary is not None,
            "implementation_lock_summary": implementation_lock_summary,
            "fit_authorized": fit_authorized,
            "future_outcomes_accessed": bool(authority["future_outcomes_accessed"]),
            "historical_outcome_manifest_semantic_decode": False,
        }
    )
    return runtime, summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_RUNTIME_CONFIG)
    parser.add_argument("--schema", type=Path, default=DEFAULT_RUNTIME_SCHEMA)
    parser.add_argument(
        "--require-restored-development-sources",
        action="store_true",
        help="Hash restored panel and expert-state development sources without decoding rows",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    _, summary = load_and_validate_development_runtime(
        args.config,
        args.schema,
        require_restored_development_sources=args.require_restored_development_sources,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
