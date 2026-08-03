from __future__ import annotations

import copy
from collections.abc import MutableMapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest

import src.experiments.closure_runtime_contract as runtime_contract
from src.experiments.build_pipe_sequences import (
    INPUT_SURFACE_ADAPTIVE_NO_CURRENT_CHLA,
    INPUT_SURFACE_NO_CURRENT_CHLA,
    _target_state_mapping,
)
from src.experiments.closure_contract import load_json_mapping, load_yaml_mapping
from src.experiments.closure_runtime_contract import (
    DEFAULT_RUNTIME_CONFIG,
    DEFAULT_RUNTIME_SCHEMA,
    EXPECTED_ANFIS_CONFIGURATION,
    EXPECTED_ANFIS_FEATURE_TRANSFORMATIONS,
    EXPECTED_ANFIS_INITIALIZATION,
    EXPECTED_ANFIS_PANEL_ANCHOR_JOIN,
    EXPECTED_ANFIS_PANEL_COLUMNS,
    EXPECTED_ANFIS_SAMPLING,
    EXPECTED_ANFIS_UNCERTAINTY_PROXY,
    EXPECTED_INPUT_COLUMNS,
    EXPECTED_MODULE_OFFSETS,
    EXPECTED_P0_STATE_MAPPING,
    EXPECTED_P1_STATE_MAPPING,
    EXPECTED_PLANNED_ARTIFACT_PATHS_SHA256,
    EXPECTED_ROLLOUT_RNG,
    EXPECTED_ROLLOUT_KERNEL,
    EXPECTED_ROLLOUT_STATE_CLIP,
    EXPECTED_SEASONALITY,
    EXPECTED_SEEDS,
    EXPECTED_TARGET_TO_NEXT_INPUT_MAPPING,
    EXPECTED_TEMPORAL_ARCHITECTURE,
    EXPECTED_TARGET_COLUMNS,
    ClosureRuntimeContractError,
    anfis_uncertainty_golden_vector,
    anfis_uncertainty_proxy,
    closure_anfis_features,
    closure_rollout_recursive_golden_vector,
    closure_rollout_scalar_step,
    anfis_module_substreams,
    anfis_hash_rank_golden_vector,
    anfis_hash_rank_sample,
    closure_seasonality,
    closure_state_deltas,
    load_and_validate_development_runtime,
    render_runtime_artifact_paths,
    rollout_origin_seed,
    rollout_predraw_sha256,
    rollout_standard_normal_predraw,
    validate_autoregressive_state_mapping,
    validate_anfis_raw_projection_columns,
    validate_development_runtime,
    validate_seed_slots,
)


PROTOCOL_LOCK_PATH = Path("reports/closure_v1/00_protocol/protocol_lock.json")


def _runtime() -> dict[str, Any]:
    return load_yaml_mapping(DEFAULT_RUNTIME_CONFIG)


def _schema() -> dict[str, Any]:
    return load_json_mapping(DEFAULT_RUNTIME_SCHEMA)


def _set_nested(payload: MutableMapping[str, Any], path: Sequence[str | int], value: Any) -> None:
    current: Any = payload
    for key in path[:-1]:
        current = current[key]
    current[path[-1]] = value


def test_public_runtime_contract_cross_validates_locked_protocol_without_fit() -> None:
    runtime, summary = load_and_validate_development_runtime()

    assert runtime["status"] == "ready_to_lock"
    assert summary["cross_validated_locked_contract"] is True
    assert summary["protocol_component_count"] == 13
    assert summary["development_location_count"] == 353
    assert summary["holdout_location_count"] == 88
    assert summary["seed_count"] == 5
    assert summary["rendered_seed_artifact_count"] == 201
    authority = runtime["authority"]
    lock = runtime["implementation_lock"]
    assert summary["common_origin_materialized"] is Path(
        authority["common_origin_manifest_path"]
    ).is_file()
    assert summary["common_origin_completion_manifest_present"] is Path(
        authority["common_origin_completion_manifest_path"]
    ).is_file()
    assert summary["implementation_lock_present"] is Path(lock["lock_manifest_path"]).is_file()
    assert summary["fit_authorized"] is False
    assert summary["future_outcomes_accessed"] is False
    assert summary["historical_outcome_manifest_semantic_decode"] is False
    assert summary["restored_development_sources_verified"] is False
    assert summary["restored_development_source_paths_verified"] == []
    assert summary["planned_artifact_paths_sha256"] == EXPECTED_PLANNED_ARTIFACT_PATHS_SHA256
    assert summary["rollout_predraw_golden_sha256"] == EXPECTED_ROLLOUT_RNG[
        "golden_predraw"
    ]["sha256"]
    assert summary["config_path"] == DEFAULT_RUNTIME_CONFIG.as_posix()
    assert summary["schema_path"] == DEFAULT_RUNTIME_SCHEMA.as_posix()


def test_runtime_schema_is_closed_draft_2020_12() -> None:
    schema = _schema()

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])


def test_alternative_permissive_schema_cannot_bypass_the_authoritative_contract() -> None:
    permissive_schema = {"$schema": "https://json-schema.org/draft/2020-12/schema"}

    with pytest.raises(ClosureRuntimeContractError, match="authoritative Closure runtime schema"):
        validate_development_runtime(
            _runtime(),
            permissive_schema,
            cross_validate_locked=False,
        )


@pytest.mark.parametrize(
    ("path", "invalid_value"),
    [
        (("status",), "locked"),
        (("authority", "locked_protocol_amended"), True),
        (("authority", "future_outcomes_accessed"), True),
        (("development_scope", "fit_target_end"), "2019-01"),
        (("development_scope", "post_2021_materialization_in_e0_d"), "allowed"),
        (("seeds", "cross_product_policy"), "allowed"),
        (("seeds", "best_seed_selection"), "minimum_validation_loss"),
        (("anfis", "fixed_configuration", "epochs"), 80),
        (("anfis", "fixed_configuration", "train_rows_per_module"), 16384),
        (("anfis", "primary_modules"), ["ANFIS-N", "ANFIS-F", "ANFIS-T"]),
        (("anfis", "irc_weights", "gamma_yT_no_chla"), 2.0),
        (("primary_autoregressive_state", "optional_context_columns"), ["x_irc1_adaptive"]),
        (
            ("primary_autoregressive_state", "model_state_mappings", "P1", "target_state_mapping", "yT"),
            "yT_adaptive",
        ),
        (("anfis", "sampling", "algorithm"), "numpy_random_sample"),
        (("temporal_models", "optimization", "early_stopping_patience_epochs"), 0),
        (("scientific_outcomes", "autoregressive_tensor_use"), "allowed"),
        (("legacy_denials", "build_pipe_sequences_legacy_mapping"), "allowed"),
    ],
    ids=[
        "status",
        "amendment",
        "future-outcomes",
        "fit-boundary",
        "post-2021",
        "seed-cross-product",
        "best-seed",
        "epochs",
        "train-size",
        "current-chla-module",
        "irc-weights",
        "optional-context",
        "adaptive-full-target",
        "sampling-algorithm",
        "early-stopping",
        "outcome-in-state",
        "legacy-mapping",
    ],
)
def test_closed_schema_rejects_runtime_decision_drift(
    path: tuple[str | int, ...],
    invalid_value: Any,
) -> None:
    runtime = copy.deepcopy(_runtime())
    _set_nested(runtime, path, invalid_value)

    with pytest.raises(ClosureRuntimeContractError, match="const|runtime contract"):
        validate_development_runtime(runtime, _schema(), cross_validate_locked=False)


def test_closed_schema_rejects_unregistered_top_level_field() -> None:
    runtime = copy.deepcopy(_runtime())
    runtime["fit_now"] = True

    with pytest.raises(ClosureRuntimeContractError, match="additionalProperties"):
        validate_development_runtime(runtime, _schema(), cross_validate_locked=False)


def test_seed_slots_are_one_to_one_and_ordered() -> None:
    slots = validate_seed_slots(_runtime()["seeds"]["ordered_slots"])

    assert tuple(slot["base_seed"] for slot in slots) == EXPECTED_SEEDS
    assert all(
        slot["base_seed"]
        == slot["anfis_base_seed"]
        == slot["p0_model_seed"]
        == slot["p1_model_seed"]
        for slot in slots
    )


def test_seed_slot_rejects_cross_pairing_even_without_schema() -> None:
    slots = copy.deepcopy(_runtime()["seeds"]["ordered_slots"])
    slots[0]["p1_model_seed"] = slots[1]["base_seed"]

    with pytest.raises(ClosureRuntimeContractError, match="seed slot 1"):
        validate_seed_slots(slots)


def test_seed_slot_rejects_extra_keys_even_without_schema() -> None:
    slots = copy.deepcopy(_runtime()["seeds"]["ordered_slots"])
    slots[0]["replacement_seed"] = 1

    with pytest.raises(ClosureRuntimeContractError, match="unexpected schema"):
        validate_seed_slots(slots)


@pytest.mark.parametrize("invalid_seed", [True, 1729.0, "1729"])
def test_seed_helpers_reject_coercible_non_integer_values(invalid_seed: Any) -> None:
    slots = copy.deepcopy(_runtime()["seeds"]["ordered_slots"])
    slots[0]["base_seed"] = invalid_seed

    with pytest.raises(ClosureRuntimeContractError, match="exact integers"):
        validate_seed_slots(slots)
    with pytest.raises(ClosureRuntimeContractError, match="Unregistered"):
        anfis_module_substreams(invalid_seed)


def test_typed_runtime_contract_rejects_integer_float_equivalence() -> None:
    runtime = copy.deepcopy(_runtime())
    runtime["anfis"]["fixed_configuration"]["epochs"] = 60.0

    with pytest.raises(ClosureRuntimeContractError, match="wrong scalar/container type"):
        validate_development_runtime(runtime, _schema(), cross_validate_locked=False)


def test_anfis_substreams_are_fixed_and_seed_scoped() -> None:
    for base_seed in EXPECTED_SEEDS:
        observed = anfis_module_substreams(base_seed)
        assert observed == {
            module: base_seed + offset
            for module, offset in EXPECTED_MODULE_OFFSETS.items()
        }
        assert len(set(observed.values())) == 3

    with pytest.raises(ClosureRuntimeContractError, match="Unregistered"):
        anfis_module_substreams(1)


def test_fixed_anfis_profile_matches_promoted_completed_wqp_run() -> None:
    anfis = _runtime()["anfis"]
    runtime_config = anfis["fixed_configuration"]

    assert runtime_config == EXPECTED_ANFIS_CONFIGURATION
    assert anfis["model_initialization"] == EXPECTED_ANFIS_INITIALIZATION
    assert anfis["uncertainty_proxy"] == EXPECTED_ANFIS_UNCERTAINTY_PROXY
    assert anfis["sampling"] == EXPECTED_ANFIS_SAMPLING
    assert anfis["sampling_seed_equals_optimization_seed"] is True
    assert anfis["seed_set_before_model_construction"] is True
    assert runtime_config["epochs"] == 60
    assert runtime_config["train_rows_per_module"] == 4096
    assert _runtime()["anfis"]["configuration_policy"] == "fixed_promoted_wqp_profile_without_search"
    assert _runtime()["anfis"]["e7_training_size_sensitivity"]["primary_model_selection_use"] == "forbidden"


def test_primary_anfis_excludes_current_chla_module_and_features() -> None:
    anfis = _runtime()["anfis"]

    assert anfis["primary_modules"] == ["ANFIS-N", "ANFIS-F", "ANFIS-T-no-current"]
    assert anfis["forbidden_primary_modules"] == ["ANFIS-T"]
    flattened_features = {
        feature
        for features in anfis["primary_module_features"].values()
        for feature in features
    }
    assert "current_chla_pressure" not in flattened_features
    assert anfis["primary_module_targets"]["ANFIS-T-no-current"] == "yT_no_chla"


@pytest.mark.parametrize(
    ("model_id", "expected"),
    [("P0", EXPECTED_P0_STATE_MAPPING), ("P1", EXPECTED_P1_STATE_MAPPING)],
)
def test_strict_state_mappings_are_accepted_for_inputs_and_targets(
    model_id: str,
    expected: dict[str, str],
) -> None:
    state = _runtime()["primary_autoregressive_state"]
    mappings = state["model_state_mappings"][model_id]
    observed = mappings["input_state_mapping"]

    assert validate_autoregressive_state_mapping(model_id, observed) == expected
    assert mappings["target_state_mapping"] == expected
    assert mappings["target_to_next_input_mapping"] == EXPECTED_TARGET_TO_NEXT_INPUT_MAPPING
    assert state["target_mapping_policy"]["input_and_target_use_same_mapping"] is True
    assert state["target_mapping_policy"]["target_columns_reused_as_next_rollout_input"] is True


@pytest.mark.parametrize(
    ("model_id", "mapping", "channel", "full_source"),
    [
        ("P0", EXPECTED_P0_STATE_MAPPING, "yT", "yT"),
        ("P0", EXPECTED_P0_STATE_MAPPING, "sigma_T", "sigma_T"),
        ("P0", EXPECTED_P0_STATE_MAPPING, "delta_yT", "delta_yT"),
        ("P1", EXPECTED_P1_STATE_MAPPING, "yT", "yT_adaptive"),
        ("P1", EXPECTED_P1_STATE_MAPPING, "sigma_T", "sigma_T_adaptive"),
        ("P1", EXPECTED_P1_STATE_MAPPING, "delta_yT", "delta_yT_adaptive"),
    ],
)
def test_full_chla_state_is_rejected_as_autoregressive_target(
    model_id: str,
    mapping: dict[str, str],
    channel: str,
    full_source: str,
) -> None:
    contaminated = dict(mapping)
    contaminated[channel] = full_source

    with pytest.raises(ClosureRuntimeContractError, match="state mapping"):
        validate_autoregressive_state_mapping(model_id, contaminated)


@pytest.mark.parametrize(
    ("model_id", "surface", "expected_full_sources"),
    [
        ("P0", INPUT_SURFACE_NO_CURRENT_CHLA, ("yT", "sigma_T", "delta_yT")),
        (
            "P1",
            INPUT_SURFACE_ADAPTIVE_NO_CURRENT_CHLA,
            ("yT_adaptive", "sigma_T_adaptive", "delta_yT_adaptive"),
        ),
    ],
)
def test_legacy_no_current_target_mappings_are_explicitly_rejected(
    model_id: str,
    surface: str,
    expected_full_sources: tuple[str, str, str],
) -> None:
    legacy = _target_state_mapping(surface)

    assert (legacy["yT"], legacy["sigma_T"], legacy["delta_yT"]) == expected_full_sources
    with pytest.raises(ClosureRuntimeContractError, match=f"{model_id} state mapping"):
        validate_autoregressive_state_mapping(model_id, legacy)


def test_autoregressive_columns_are_exact_and_context_free() -> None:
    state = _runtime()["primary_autoregressive_state"]

    assert tuple(state["input_columns"]) == EXPECTED_INPUT_COLUMNS
    assert tuple(state["target_columns"]) == EXPECTED_TARGET_COLUMNS
    assert state["optional_context_columns"] == []
    assert len(state["input_columns"]) == 13
    assert len(state["target_columns"]) == 9


def test_no_current_state_targets_are_separate_from_scientific_outcomes() -> None:
    runtime = _runtime()
    state = runtime["primary_autoregressive_state"]
    outcomes = runtime["scientific_outcomes"]
    mappings = state["model_state_mappings"]
    state_sources = set(mappings["P0"]["target_state_mapping"].values()) | set(
        mappings["P1"]["target_state_mapping"].values()
    )
    outcome_sources = set(outcomes["source_columns"].values())

    assert state_sources.isdisjoint(outcome_sources)
    assert outcomes["join_stage"] == "after_autoregressive_sequence_is_frozen"
    assert outcomes["autoregressive_tensor_use"] == "forbidden"
    assert outcomes["predictor_use"] == "forbidden"
    assert outcomes["post_2021_access_before_e0_u"] == "forbidden"


def test_anfis_reads_only_the_exact_no_chla_raw_projection() -> None:
    projection = _runtime()["anfis"]["source_projection"]

    assert tuple(projection["panel_columns"]) == EXPECTED_ANFIS_PANEL_COLUMNS
    assert projection["panel_anchor_join"] == EXPECTED_ANFIS_PANEL_ANCHOR_JOIN
    validate_anfis_raw_projection_columns(
        projection["panel_columns"],
        projection["expert_anchor_columns"],
    )
    assert projection["projection_at_parquet_read_required"] is True
    assert projection["generic_full_feature_builder_use"] == "forbidden"
    assert projection["panel_path"] == "data/panel/panel_monthly_v0.parquet"
    assert projection["expert_anchor_path"] == "data/fuzzy/state_vector_v0.parquet"
    assert "mean_chlorophyll_a_ugL" not in projection["panel_columns"]
    assert "mean_chlorophyll_a_ugL" in projection["forbidden_exact_columns"]
    assert "yT" not in projection["expert_anchor_columns"]
    assert projection["derived_feature_lineage"]["temp_favorable"] == ["mean_temperature_C"]
    assert projection["derived_feature_transformations"] == EXPECTED_ANFIS_FEATURE_TRANSFORMATIONS


def test_anfis_physical_projection_validator_rejects_extra_or_reordered_columns() -> None:
    projection = _runtime()["anfis"]["source_projection"]
    panel_columns = list(projection["panel_columns"])
    expert_anchor_columns = list(projection["expert_anchor_columns"])

    with pytest.raises(ClosureRuntimeContractError, match="ANFIS panel physical projection"):
        validate_anfis_raw_projection_columns(
            [*panel_columns, "mean_chlorophyll_a_ugL"],
            expert_anchor_columns,
        )
    with pytest.raises(ClosureRuntimeContractError, match="ANFIS expert-anchor physical projection"):
        validate_anfis_raw_projection_columns(
            panel_columns,
            list(reversed(expert_anchor_columns)),
        )


def test_anfis_derived_features_match_the_golden_transform_vector() -> None:
    observed = closure_anfis_features(
        {
            "mean_TP_ugL": 100.0,
            "mean_TN_ugL": 300.0,
            "TN_TP_ratio": 12.0,
            "mean_DO_mgL": 7.0,
            "mean_pH": 8.0,
            "mean_turbidity_NTU": 27.5,
            "mean_secchi_depth_m": 1.75,
            "mean_temperature_C": 30.0,
            "mean_chlorophyll_a_ugL": 9999.0,
        }
    )

    assert observed == {
        "tp_pressure": 1.0,
        "tn_pressure": 0.0,
        "ratio_imbalance_pressure": 0.5,
        "do_good": 1.0,
        "ph_good": 1.0,
        "turbidity_good": 0.5,
        "secchi_good": 0.5,
        "temp_favorable": 1.0,
    }
    missing = closure_anfis_features({"mean_TP_ugL": -1.0})
    assert missing["tp_pressure"] is None
    assert all(
        value is None
        for key, value in missing.items()
        if key != "tp_pressure"
    )


def test_anfis_uncertainty_proxy_matches_closed_golden_vectors() -> None:
    golden_vectors = EXPECTED_ANFIS_UNCERTAINTY_PROXY["golden_vectors"]

    assert anfis_uncertainty_golden_vector() == pytest.approx(
        [vector["sigma"] for vector in golden_vectors]
    )
    assert anfis_uncertainty_proxy(
        [0.25] * 27,
        module="ANFIS-N",
        missing_fraction=0.0,
    ) == pytest.approx(0.55)
    assert anfis_uncertainty_proxy(
        [0.5] * 81,
        module="ANFIS-F",
        missing_fraction=0.2,
    ) == pytest.approx(0.62)
    assert anfis_uncertainty_proxy(
        [0.0, 0.0, 0.0],
        module="ANFIS-T-no-current",
        missing_fraction=0.0,
    ) == pytest.approx(0.1)


@pytest.mark.parametrize(
    ("firing_strengths", "module", "missing_fraction", "error"),
    [
        ([], "ANFIS-T-no-current", 0.0, "exactly 3"),
        ([True, 0.0, 0.0], "ANFIS-T-no-current", 0.0, "ANFIS firing strengths"),
        ([0.5, float("nan"), 0.5], "ANFIS-T-no-current", 0.0, "ANFIS firing strengths"),
        ([1.0, 0.0, 0.0], "ANFIS-T-no-current", True, "missing_fraction"),
        ([1.0], "ANFIS-X", 0.0, "Unregistered primary"),
    ],
)
def test_anfis_uncertainty_proxy_rejects_empty_nonfinite_and_boolean_inputs(
    firing_strengths: list[Any],
    module: str,
    missing_fraction: Any,
    error: str,
) -> None:
    with pytest.raises(ClosureRuntimeContractError, match=error):
        anfis_uncertainty_proxy(
            firing_strengths,
            module=module,
            missing_fraction=missing_fraction,
        )


def test_state_exports_have_exact_no_current_allowlists_and_audit_flag() -> None:
    export = _runtime()["primary_autoregressive_state"]["state_export"]

    assert export["bounded_export"] == "forbidden"
    assert export["latest_state_month"] == "2021-12"
    assert export["p0_output_columns"][3] == "time_role"
    assert export["p1_output_columns"][3] == "time_role"
    assert "development_role" not in export["p0_output_columns"]
    assert "development_role" not in export["p1_output_columns"]
    assert "delta_previous_month_missing" in export["p0_output_columns"]
    assert "delta_previous_month_missing" in export["p1_output_columns"]
    assert {"yT", "sigma_T", "delta_yT"}.isdisjoint(export["p0_output_columns"])
    assert {"yT_adaptive", "sigma_T_adaptive", "delta_yT_adaptive"}.isdisjoint(
        export["p1_output_columns"]
    )


def test_temporal_profile_closes_architecture_early_stopping_and_rollout() -> None:
    temporal = _runtime()["temporal_models"]

    assert temporal["common_architecture"] == EXPECTED_TEMPORAL_ARCHITECTURE
    assert temporal["optimization"]["maximum_epochs"] == 20
    assert temporal["optimization"]["early_stopping_patience_epochs"] == 5
    assert temporal["optimization"]["restore_best_checkpoint"] is True
    assert temporal["windows"]["use_all_training_windows"] is True
    assert temporal["windows"]["history_context_may_precede_endpoint_role"] is True
    assert temporal["windows"]["history_context_rows_contribute_loss"] is False
    assert temporal["windows"]["test_or_locked_evaluation_window_materialization"] == "forbidden"
    assert temporal["windows"]["canonical_window_order"] == [
        "source_id_utf8_ascending",
        "site_id_utf8_ascending",
        "origin_year_month_ascending",
        "target_year_month_ascending",
    ]
    assert temporal["windows"]["canonical_order_applied_before_shuffle"] is True
    assert temporal["rollout"]["samples_per_origin"] == 128
    assert temporal["rollout"]["rng"] == EXPECTED_ROLLOUT_RNG
    assert temporal["rollout"]["kernel"] == EXPECTED_ROLLOUT_KERNEL
    assert temporal["rollout"]["state_clip_by_channel"] == EXPECTED_ROLLOUT_STATE_CLIP
    assert temporal["rollout"]["state_clip_by_channel"]["delta_yT"] == [-1.0, 1.0]
    assert temporal["training_randomness"]["dataloader"]["epoch_seed_formula"] == (
        "base_seed_plus_one_based_epoch"
    )
    assert temporal["training_randomness"]["automatic_device_selection"] == "forbidden"
    assert temporal["loss"]["reduction"] == "arithmetic_mean_over_all_rows_and_nine_targets"
    assert temporal["loss"]["training_mu_use"] == "unblended_model_mu"
    assert temporal["checkpoint_selection"]["persistence_scale_floor"] == 1e-12
    assert temporal["checkpoint_selection"]["epoch_cycle"] == [
        "train_on_unblended_loss",
        "fit_provisional_blend_on_model_selection",
        "evaluate_blended_model_selection_metrics",
        "compare_checkpoint_objective",
    ]
    assert temporal["checkpoint_selection"]["strict_improvement_operator"] == "less_than"
    assert temporal["checkpoint_selection"]["provisional_blend_recomputed_each_epoch"] is True
    assert temporal["checkpoint_selection"]["best_checkpoint_stores_unblended_model_state"] is True
    assert temporal["checkpoint_selection"]["final_blend_after_restore"] == (
        "recompute_once_on_model_selection_and_persist"
    )
    assert temporal["checkpoint_selection"]["final_blend_replaces_provisional"] is True
    assert temporal["output_blend"]["grid_scale_floor"] == 1e-12
    assert temporal["preprocessing"]["dtype"] == "float32"
    assert {
        key: temporal["rollout"]["kernel"][key]
        for key in (
            "model_input_dtype",
            "model_output_dtype",
            "epsilon_dtype",
            "blend_variance_sampling_dtype",
            "clip_dtype",
            "recycled_state_cast",
            "seasonality_cast",
            "next_model_window_dtype",
        )
    } == {
        "model_input_dtype": "float32",
        "model_output_dtype": "float32",
        "epsilon_dtype": "float64",
        "blend_variance_sampling_dtype": (
            "float64_after_casting_model_outputs_and_persistence"
        ),
        "clip_dtype": "float64",
        "recycled_state_cast": "float32_after_clip_before_window_append",
        "seasonality_cast": "float64_calculation_then_float32_before_window_append",
        "next_model_window_dtype": "float32",
    }
    assert temporal["rollout"]["irc_weights"] == {
        "alpha_yN": 1.0,
        "beta_one_minus_yF": 1.0,
        "gamma_yT_no_chla": 1.0,
    }


def test_seasonality_formula_is_exact_and_calendar_based() -> None:
    assert _runtime()["primary_autoregressive_state"]["seasonality"] == EXPECTED_SEASONALITY
    assert closure_seasonality(1) == {
        "season_sin_annual": 0.0,
        "season_cos_annual": 1.0,
        "season_sin_semiannual": 0.0,
        "season_cos_semiannual": 1.0,
    }
    april = closure_seasonality(4)
    assert april["season_sin_annual"] == pytest.approx(1.0)
    assert april["season_cos_annual"] == pytest.approx(0.0, abs=1e-15)
    assert april["season_sin_semiannual"] == pytest.approx(0.0, abs=1e-15)
    assert april["season_cos_semiannual"] == pytest.approx(-1.0)

    with pytest.raises(ClosureRuntimeContractError, match="calendar_month"):
        closure_seasonality(0)
    with pytest.raises(ClosureRuntimeContractError, match="calendar_month"):
        closure_seasonality(True)


def test_rollout_origin_seed_has_a_golden_payload_and_is_batch_order_invariant() -> None:
    expected = int("da2608799b166888a8939b5a4657bc02", 16)
    first = rollout_origin_seed(
        1729,
        source_id="wqp",
        site_id="A",
        origin_year_month="2020-01",
    )
    reordered = [
        rollout_origin_seed(
            1729,
            source_id="wqp",
            site_id=site_id,
            origin_year_month=month,
        )
        for site_id, month in [("B", "2020-02"), ("A", "2020-01")]
    ]

    assert first == expected
    assert reordered[1] == expected
    assert rollout_origin_seed(
        1729,
        source_id="wqp",
        site_id="A",
        origin_year_month="2020-01",
    ) == first


def test_rollout_predraw_has_locked_shape_dtype_order_and_digest() -> None:
    predraw = rollout_standard_normal_predraw(
        1729,
        source_id="wqp",
        site_id="A",
        origin_year_month="2020-01",
    )

    assert predraw.shape == (3, 128, 9)
    assert predraw.dtype == np.float64
    assert rollout_predraw_sha256(predraw) == EXPECTED_ROLLOUT_RNG["golden_predraw"][
        "sha256"
    ]


def test_rollout_predraw_hash_rejects_shape_dtype_and_nonfinite_drift() -> None:
    with pytest.raises(ClosureRuntimeContractError, match="shape"):
        rollout_predraw_sha256(np.zeros((1, 128, 9), dtype=np.float64))
    with pytest.raises(ClosureRuntimeContractError, match="float64"):
        rollout_predraw_sha256(np.zeros((3, 128, 9), dtype=np.float32))
    nonfinite = np.zeros((3, 128, 9), dtype=np.float64)
    nonfinite[0, 0, 0] = np.nan
    with pytest.raises(ClosureRuntimeContractError, match="finite"):
        rollout_predraw_sha256(nonfinite)


def test_rollout_recursive_golden_vector_locks_float32_recycling() -> None:
    assert closure_rollout_recursive_golden_vector() == EXPECTED_ROLLOUT_KERNEL[
        "recursive_golden_vector"
    ]["recycled_float32_states"]


def test_validator_rejects_uncertainty_golden_recomputation_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def drifted_uncertainty() -> list[float]:
        return [0.0, 0.0, 0.0]

    monkeypatch.setattr(
        runtime_contract,
        "anfis_uncertainty_golden_vector",
        drifted_uncertainty,
    )
    with pytest.raises(ClosureRuntimeContractError, match="uncertainty golden"):
        validate_development_runtime(_runtime(), _schema())


def test_validator_rejects_predraw_golden_recomputation_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def drifted_predraw(
        base_seed: int,
        *,
        source_id: str,
        site_id: str,
        origin_year_month: str,
    ) -> np.ndarray:
        del base_seed, source_id, site_id, origin_year_month
        return np.zeros((3, 128, 9), dtype=np.float64)

    monkeypatch.setattr(
        runtime_contract,
        "rollout_standard_normal_predraw",
        drifted_predraw,
    )
    with pytest.raises(ClosureRuntimeContractError, match="predraw golden"):
        validate_development_runtime(_runtime(), _schema())


def test_validator_rejects_recursive_golden_recomputation_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def drifted_recursive_vector() -> list[float]:
        return [0.0, 0.0]

    monkeypatch.setattr(
        runtime_contract,
        "closure_rollout_recursive_golden_vector",
        drifted_recursive_vector,
    )
    with pytest.raises(ClosureRuntimeContractError, match="recursive float32 golden"):
        validate_development_runtime(_runtime(), _schema())


def test_rollout_scalar_kernel_blends_samples_and_preserves_signed_deltas() -> None:
    assert closure_rollout_scalar_step(
        channel="yN",
        persistence=0.2,
        mu=0.6,
        log_variance=0.0,
        blend_weight=0.5,
        epsilon=0.1,
    ) == pytest.approx(0.5)
    assert closure_rollout_scalar_step(
        channel="delta_yT",
        persistence=-0.2,
        mu=-0.6,
        log_variance=0.0,
        blend_weight=0.5,
        epsilon=-0.8,
    ) == -1.0
    assert closure_rollout_scalar_step(
        channel="delta_yN",
        persistence=0.0,
        mu=0.0,
        log_variance=100.0,
        blend_weight=0.0,
        epsilon=0.1,
    ) == pytest.approx(0.1 * 2.718281828459045)


def test_rollout_scalar_kernel_rejects_invalid_or_non_float32_model_values() -> None:
    with pytest.raises(ClosureRuntimeContractError, match="finite numeric"):
        closure_rollout_scalar_step(
            channel="yN",
            persistence=0.0,
            mu=0.0,
            log_variance=0.0,
            blend_weight=0.5,
            epsilon=True,
        )
    with pytest.raises(ClosureRuntimeContractError, match="blend_weight"):
        closure_rollout_scalar_step(
            channel="yN",
            persistence=0.0,
            mu=0.0,
            log_variance=0.0,
            blend_weight=1.1,
            epsilon=0.0,
        )
    with pytest.raises(ClosureRuntimeContractError, match="representable as float32"):
        closure_rollout_scalar_step(
            channel="yN",
            persistence=0.0,
            mu=1e300,
            log_variance=0.0,
            blend_weight=0.5,
            epsilon=0.0,
        )


def test_outcome_join_retains_unavailable_targets_and_declares_shared_lineage() -> None:
    outcomes = _runtime()["scientific_outcomes"]

    assert outcomes["independence_claim_between_outcomes"] == "forbidden"
    assert outcomes["join_policy"]["join_type"] == "left"
    assert outcomes["join_policy"]["relationship"] == "one_to_one"
    assert outcomes["join_policy"]["unmatched_origin_policy"] == "retain_with_target_unavailable"
    assert outcomes["join_policy"]["inner_join_row_drop"] == "forbidden"
    assert outcomes["trophic_references"]["e4a_future_chla_proxy_v0"] == "available_target_only"
    assert outcomes["trophic_references"]["e4b_tsi_non_chla"] == "pending_separate_contract"


def test_artifact_paths_resolve_locked_logical_paths_and_cover_evidence() -> None:
    artifacts = _runtime()["artifacts"]
    resolution = artifacts["logical_path_resolution"]
    slots = validate_seed_slots(_runtime()["seeds"]["ordered_slots"])
    paths, digest = render_runtime_artifact_paths(_runtime(), slots)

    assert resolution["concrete_adaptive_state_template"] == artifacts["anfis_state_template"]
    assert resolution["concrete_adaptive_sequence_template"] == artifacts["adaptive_sequence_template"]
    assert artifacts["expert_state_path"].endswith("expert_no_current_state.parquet")
    assert "anfis_manifest_template" in artifacts
    assert "pipe_checkpoint_template" in artifacts
    assert "pipe_preprocessor_contract_template" in artifacts
    assert "pipe_training_curve_template" in artifacts
    assert "pipe_blend_search_template" in artifacts
    assert len(paths) == artifacts["planned_concrete_path_count"] == 201
    assert paths == sorted(paths, key=lambda value: value.encode("utf-8"))
    assert digest == artifacts["planned_concrete_paths_sha256"]
    assert digest == EXPECTED_PLANNED_ARTIFACT_PATHS_SHA256
    assert artifacts["external_lock_persists_expanded_path_records"] is True
    assert artifacts["pre_e0_dl_heavy_path_policy"] == (
        "planned_paths_and_dvc_ownership_only"
    )
    assert artifacts["unmaterialized_dvc_pointer_creation"] == "forbidden"
    assert artifacts["post_fit_heavy_dvc_registration"] == (
        "required_before_artifact_commit_and_e0_m"
    )


@pytest.mark.parametrize(
    ("field", "invalid_path", "error"),
    [
        ("expert_state_path", "data/closure_v1/../escape.parquet", "not canonical"),
        ("expert_state_path", "data/closure_v1/./expert.parquet", "not canonical"),
        ("expert_state_path", "other/output.parquet", "unauthorized root"),
    ],
)
def test_artifact_path_renderer_rejects_traversal_aliases_and_unknown_roots(
    field: str,
    invalid_path: str,
    error: str,
) -> None:
    runtime = copy.deepcopy(_runtime())
    runtime["artifacts"][field] = invalid_path
    slots = validate_seed_slots(runtime["seeds"]["ordered_slots"])

    with pytest.raises(ClosureRuntimeContractError, match=error):
        render_runtime_artifact_paths(runtime, slots)


def test_artifact_path_renderer_rejects_canonical_collisions() -> None:
    runtime = copy.deepcopy(_runtime())
    runtime["artifacts"]["expert_state_manifest_path"] = runtime["artifacts"][
        "expert_state_path"
    ]
    slots = validate_seed_slots(runtime["seeds"]["ordered_slots"])

    with pytest.raises(ClosureRuntimeContractError, match="colliding canonical"):
        render_runtime_artifact_paths(runtime, slots)


def test_external_runtime_lock_is_required_but_not_yet_authorization() -> None:
    lock = _runtime()["implementation_lock"]

    assert lock["gate"] == "E0-DL"
    assert lock["contract_publication_state"] == "pending_adapters_common_origin_and_locker"
    assert lock["external_lock_bundle_committed_before_fit"] is True
    assert lock["require_full_type_check"] is True
    assert lock["require_restored_development_source_hashes"] is True
    assert lock["runtime_dependency_hash_policy"] == (
        "recursive_repository_local_import_closure"
    )
    assert lock["external_lock_records_each_dependency_path_sha256"] is True
    assert "src/experiments/train_pipe_grud.py" in lock["required_legacy_dependency_paths"]
    assert "src/experiments/rollout_pipe_grud.py" in lock["required_legacy_dependency_paths"]
    assert lock["required_authorization_fields"] == {
        "development_fit_authorized": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
    }
    assert lock["does_not_replace_e0_m_model_lock"] is True


def test_delta_contract_requires_exact_previous_calendar_month() -> None:
    policy = _runtime()["primary_autoregressive_state"]["delta_policy"]

    assert policy == {
        "operation": "current_minus_previous_calendar_month",
        "exact_previous_calendar_month_required": True,
        "previous_available_row_substitution": "forbidden",
        "missing_exact_previous_calendar_month": "zero_all_three_deltas_and_set_audit_flag",
        "audit_flag_column": "delta_previous_month_missing",
        "audit_flag_model_tensor_use": "forbidden",
        "audit_flag_manifest_count": "required",
        "interior_history_gap_policy": "exclude_origin_via_common_origin_contract",
        "precomputed_full_chla_delta": "forbidden",
    }


def test_strict_p0_deltas_use_all_three_no_current_channels_and_exact_months() -> None:
    rows = [
        {
            "source_id": "wqp", "site_id": "A", "year_month": "2020-03",
            "yN": 0.8, "yF": 0.8, "yT_no_chla": 0.8,
        },
        {
            "source_id": "wqp", "site_id": "B", "year_month": "2020-02",
            "yN": 0.7, "yF": 0.2, "yT_no_chla": 0.6,
        },
        {
            "source_id": "wqp", "site_id": "A", "year_month": "2019-12",
            "yN": 0.2, "yF": 0.3, "yT_no_chla": 0.4,
        },
        {
            "source_id": "wqp", "site_id": "A", "year_month": "2020-01",
            "yN": 0.5, "yF": 0.1, "yT_no_chla": 0.9,
            "yT": 0.0, "delta_yT": 999.0, "delta_yT_no_chla": 999.0,
            "mean_chlorophyll_a_ugL": 9999.0,
        },
        {
            "source_id": "wqp", "site_id": "B", "year_month": "2020-01",
            "yN": 0.4, "yF": 0.4, "yT_no_chla": 0.4,
        },
    ]

    observed = closure_state_deltas(
        "P0",
        rows,
        development_keys={("wqp", "A"), ("wqp", "B")},
    )

    by_key = {(row["site_id"], row["year_month"]): row for row in observed}
    assert by_key[("A", "2020-01")]["delta_yN"] == pytest.approx(0.3)
    assert by_key[("A", "2020-01")]["delta_yF"] == pytest.approx(-0.2)
    assert by_key[("A", "2020-01")]["delta_yT_no_chla"] == pytest.approx(0.5)
    assert by_key[("A", "2020-03")]["delta_yT_no_chla"] == 0.0
    assert by_key[("A", "2020-03")]["delta_previous_month_missing"] is True
    assert by_key[("B", "2020-02")]["delta_yT_no_chla"] == pytest.approx(0.2)
    assert by_key[("B", "2020-02")]["delta_previous_month_missing"] is False
    assert set(by_key[("A", "2020-01")]) == {
        "source_id", "site_id", "year_month", "delta_yN", "delta_yF",
        "delta_yT_no_chla", "delta_previous_month_missing",
    }


def test_strict_p1_delta_ignores_poisoned_full_chla_siblings() -> None:
    rows = [
        {
            "source_id": "wqp",
            "site_id": "A",
            "year_month": "2020-01",
            "yN_adaptive": 0.1,
            "yF_adaptive": 0.8,
            "yT_no_chla_adaptive": 0.25,
            "yT_adaptive": 0.99,
            "delta_yT_adaptive": -999.0,
            "mean_chlorophyll_a_ugL": 1.0,
        },
        {
            "source_id": "wqp",
            "site_id": "A",
            "year_month": "2020-02",
            "yN_adaptive": 0.4,
            "yF_adaptive": 0.6,
            "yT_no_chla_adaptive": 0.75,
            "yT_adaptive": 0.01,
            "delta_yT_adaptive": 999.0,
            "mean_chlorophyll_a_ugL": 500.0,
        },
    ]
    perturbed = copy.deepcopy(rows)
    perturbed[0]["mean_chlorophyll_a_ugL"] = 9999.0
    perturbed[1]["mean_chlorophyll_a_ugL"] = 0.0

    original = closure_state_deltas("P1", rows, development_keys={("wqp", "A")})
    changed = closure_state_deltas("P1", perturbed, development_keys={("wqp", "A")})

    assert original == changed
    assert original[1]["delta_yN_adaptive"] == pytest.approx(0.3)
    assert original[1]["delta_yF_adaptive"] == pytest.approx(-0.2)
    assert original[1]["delta_yT_no_chla_adaptive"] == pytest.approx(0.5)


def test_strict_delta_wrapper_rejects_unknown_models_duplicates_and_bad_state() -> None:
    row = {
        "source_id": "wqp", "site_id": "A", "year_month": "2020-01",
        "yN": 0.2, "yF": 0.3, "yT_no_chla": 0.4,
    }

    with pytest.raises(ClosureRuntimeContractError, match="Unsupported Closure temporal model"):
        closure_state_deltas("P2", [row], development_keys={("wqp", "A")})
    with pytest.raises(ClosureRuntimeContractError, match="Duplicate state key"):
        closure_state_deltas("P0", [row, row], development_keys={("wqp", "A")})
    contaminated = dict(row, yT_no_chla=float("inf"))
    with pytest.raises(ClosureRuntimeContractError, match=r"finite in \[0, 1\]"):
        closure_state_deltas("P0", [contaminated], development_keys={("wqp", "A")})
    out_of_range = dict(row, yN=1.1)
    with pytest.raises(ClosureRuntimeContractError, match=r"finite in \[0, 1\]"):
        closure_state_deltas("P0", [out_of_range], development_keys={("wqp", "A")})
    boolean_state = dict(row, yF=True)
    with pytest.raises(ClosureRuntimeContractError, match=r"finite in \[0, 1\]"):
        closure_state_deltas("P0", [boolean_state], development_keys={("wqp", "A")})


def test_strict_delta_wrapper_rejects_keys_absent_from_locked_development() -> None:
    row = {
        "source_id": "wqp",
        "site_id": "A",
        "year_month": "2020-01",
        "yN": 0.2,
        "yF": 0.3,
        "yT_no_chla": 0.4,
    }

    with pytest.raises(ClosureRuntimeContractError, match="absent from the locked E0-C development set"):
        closure_state_deltas("P0", [row], development_keys=set())


def _anfis_n_candidate(site_id: Any, year_month: Any) -> dict[str, Any]:
    return {
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


def _development_keys_for(rows: Sequence[dict[str, Any]]) -> set[tuple[str, str]]:
    return {
        (cast(str, row["source_id"]), cast(str, row["site_id"]))
        for row in rows
    }


def test_hash_rank_sampling_matches_golden_payload_digests_and_order() -> None:
    first, first_audit = anfis_hash_rank_golden_vector()
    second, second_audit = anfis_hash_rank_golden_vector()

    assert first == second
    assert first_audit == second_audit
    assert first == [
        {
            "source_id": "wqp", "site_id": "B", "year_month": "2018-02",
            "module": "ANFIS-N", "module_seed": 1830,
            "rank_sha256": "12676d51c9d1321112aec68af4efa764e3271920f459cb0fae1ecd026804be2f",
        },
        {
            "source_id": "wqp", "site_id": "\u00c1", "year_month": "2018-01",
            "module": "ANFIS-N", "module_seed": 1830,
            "rank_sha256": "3965e4b3dc04c2722b626a08cc1373a4380392f939932b3da68df1d8e0c5b6c0",
        },
    ]
    assert first_audit["eligible_universe_rows"] == 3
    assert first_audit["selected_rows"] == 2
    assert first_audit["eligible_universe_sha256"] == (
        "1a2a1acfc5ec677fcf34f8e0091ecd8842957de1e1f3995176720cb143386791"
    )
    assert first_audit["selected_keys_sha256"] == (
        "0f10df1201a23036532c4b65b927113d82bb9c9a1fb00d32efe65873d2cdc7f1"
    )
    assert first_audit["module"] == "ANFIS-N"
    assert first_audit["base_seed"] == 1729


def test_hash_rank_sampler_applies_anchor_then_module_missingness_filters() -> None:
    rows = [
        *[
            _anfis_n_candidate(f"S{index:04d}", "2018-01")
            for index in range(4096)
        ],
        dict(_anfis_n_candidate("D", "2018-04"), yN=None),
        dict(_anfis_n_candidate("E", "2018-05"), tp_pressure=None, tn_pressure=None),
    ]

    first, audit = anfis_hash_rank_sample(
        rows,
        module="ANFIS-N",
        module_seed=1830,
        development_keys=_development_keys_for(rows),
    )
    second, reversed_audit = anfis_hash_rank_sample(
        list(reversed(rows)),
        module="ANFIS-N",
        module_seed=1830,
        development_keys=_development_keys_for(rows),
    )

    assert first == second
    assert audit == reversed_audit
    assert audit["input_rows"] == 4098
    assert audit["excluded_nonfinite_target_rows"] == 1
    assert audit["excluded_missingness_rows"] == 1
    assert audit["eligible_universe_rows"] == 4096
    assert audit["selected_rows"] == 4096


def test_hash_rank_sampling_rejects_duplicate_or_insufficient_keys() -> None:
    row = _anfis_n_candidate("A", "2018-01")

    with pytest.raises(ClosureRuntimeContractError, match="unique"):
        anfis_hash_rank_sample(
            [row, row],
            module="ANFIS-N",
            module_seed=1830,
            development_keys={("wqp", "A")},
        )
    with pytest.raises(ClosureRuntimeContractError, match="required"):
        anfis_hash_rank_sample(
            [row],
            module="ANFIS-N",
            module_seed=1830,
            development_keys={("wqp", "A")},
        )


def test_hash_rank_sampling_rejects_keys_absent_from_locked_development() -> None:
    row = _anfis_n_candidate("A", "2018-01")

    with pytest.raises(ClosureRuntimeContractError, match="absent from the locked E0-C development set"):
        anfis_hash_rank_sample(
            [row],
            module="ANFIS-N",
            module_seed=1830,
            development_keys=set(),
        )


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("source_id", None),
        ("site_id", 1),
        ("site_id", " A"),
        ("site_id", "e\u0301"),
        ("year_month", "2018-1"),
    ],
)
def test_hash_rank_sampling_rejects_noncanonical_immutable_keys(
    field: str,
    invalid_value: Any,
) -> None:
    row = _anfis_n_candidate("A", "2018-01")
    row[field] = invalid_value

    with pytest.raises(ClosureRuntimeContractError, match="Closure key"):
        anfis_hash_rank_sample(
            [row],
            module="ANFIS-N",
            module_seed=1830,
            development_keys=_development_keys_for([row]),
        )


@pytest.mark.parametrize(
    ("module", "module_seed", "error"),
    [
        ("ANFIS-X", 1830, "Unregistered primary"),
        ("ANFIS-N", 1831, "not paired"),
        ("ANFIS-N", True, "non-negative integer"),
    ],
)
def test_hash_rank_sampling_rejects_unlocked_modules_seeds_and_sizes(
    module: str,
    module_seed: Any,
    error: str,
) -> None:
    row = _anfis_n_candidate("A", "2018-01")

    with pytest.raises(ClosureRuntimeContractError, match=error):
        anfis_hash_rank_sample(
            [row],
            module=module,
            module_seed=module_seed,
            development_keys={("wqp", "A")},
        )


def test_production_hash_rank_sampler_has_no_size_override() -> None:
    sampler = cast(Any, anfis_hash_rank_sample)

    with pytest.raises(TypeError, match="selected_rows"):
        sampler(
            [_anfis_n_candidate("A", "2018-01")],
            module="ANFIS-N",
            module_seed=1830,
            development_keys={("wqp", "A")},
            selected_rows=1,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_id", "other"),
        ("assignment_role", "holdout"),
        ("time_role", "model_selection"),
        ("year_month", "2019-01"),
    ],
)
def test_hash_rank_sampling_rejects_rows_before_scope_filters(field: str, value: str) -> None:
    row = _anfis_n_candidate("A", "2018-01")
    row[field] = value

    with pytest.raises(ClosureRuntimeContractError, match="WQP development/training"):
        anfis_hash_rank_sample(
            [row],
            module="ANFIS-N",
            module_seed=1830,
            development_keys=_development_keys_for([row]),
        )


def test_runtime_files_are_derived_and_not_protocol_components() -> None:
    protocol_lock = load_json_mapping(PROTOCOL_LOCK_PATH)
    locked_paths = {record["path"] for record in protocol_lock["protocol_components"]}

    assert len(locked_paths) == 13
    assert DEFAULT_RUNTIME_CONFIG.as_posix() not in locked_paths
    assert DEFAULT_RUNTIME_SCHEMA.as_posix() not in locked_paths
    assert _runtime()["authority"]["locked_protocol_amended"] is False
    assert _runtime()["authority"]["runtime_lock_required_before_fit"] is True
