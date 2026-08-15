from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
import pytest

from src.experiments import build_trophic_reference_targets as e4_reference
from src.experiments import evaluate_anfis_ablation as e7
from src.experiments import evaluate_trophic_state as e4_evaluation
from src.experiments import run_closure_benchmark as runner


def _e4_future_indicators() -> pd.DataFrame:
    rows = []
    for horizon, chla in zip((1, 2, 3), (1.5, 15.0, 60.0), strict=True):
        rows.append(
            {
                "source_id": "wqp",
                "site_id": "site-1",
                "holdout_group_id": "holdout-1",
                "common_origin_id": hashlib.sha256(b"e4-origin").hexdigest(),
                "origin_year_month": "2021-12",
                "target_year_month": f"2022-{horizon:02d}",
                "horizon_months": horizon,
                "evaluation_cohort": "location_holdout",
                "evaluation_role": "test",
                "future_TP_ugL": 20.0,
                "future_secchi_depth_m": 2.0,
                "future_chlorophyll_a_ugL": chla,
            }
        )
    return pd.DataFrame(rows, columns=e4_reference.INPUT_COLUMNS)


def _e4_predictions() -> pd.DataFrame:
    rows = []
    ordinal_models = {"B1", "B2"}
    unavailable_models = {"P0", "P1"}
    origin_id = hashlib.sha256(b"e4-origin").hexdigest()
    for horizon in (1, 2, 3):
        for model_id in e4_evaluation.MODEL_IDS:
            for seed in e4_evaluation.REGISTERED_SEEDS:
                if model_id in ordinal_models:
                    terminal_status = "success"
                    ordinal_status = "success"
                    score = 0.15 + 0.25 * horizon
                    cutpoints = (0.25, 0.5, 0.75)
                elif model_id in unavailable_models:
                    terminal_status = "model_unavailable"
                    ordinal_status = "model_unavailable"
                    score = np.nan
                    cutpoints = (np.nan, np.nan, np.nan)
                else:
                    terminal_status = "success"
                    ordinal_status = "not_applicable"
                    score = np.nan
                    cutpoints = (np.nan, np.nan, np.nan)
                rows.append(
                    {
                        "source_id": "wqp",
                        "site_id": "site-1",
                        "holdout_group_id": "holdout-1",
                        "common_origin_id": origin_id,
                        "origin_year_month": "2021-12",
                        "target_year_month": f"2022-{horizon:02d}",
                        "horizon_months": horizon,
                        "evaluation_cohort": "location_holdout",
                        "evaluation_role": "test",
                        "model_id": model_id,
                        "model_seed": seed,
                        "seed_slot": seed,
                        "terminal_status": terminal_status,
                        "ordinal_status": ordinal_status,
                        "ordinal_score": score,
                        "cutpoint_1": cutpoints[0],
                        "cutpoint_2": cutpoints[1],
                        "cutpoint_3": cutpoints[2],
                    }
                )
    return pd.DataFrame(rows, columns=e4_evaluation.PREDICTION_COLUMNS)


def test_e4_keeps_locked_cohort_and_endpoint_denominators() -> None:
    references = e4_reference.build_trophic_reference_targets(_e4_future_indicators())
    evaluated = e4_evaluation.evaluate_trophic_state(_e4_predictions(), references)

    proxy = evaluated["trophic_proxy_metrics"]
    assert proxy["evaluation_cohort"].eq("location_holdout").all()
    assert proxy["evaluation_role"].eq("test").all()
    successful = proxy[proxy["model_id"].isin(["B1", "B2"])]
    assert successful["status"].eq("available").all()
    assert successful["ordinal_success_row_count"].eq(1).all()
    assert successful["evaluation_row_count"].eq(1).all()
    unavailable = proxy[proxy["model_id"].isin(["P0", "P1"])]
    assert unavailable["status"].eq("model_unavailable").all()
    assert unavailable["model_unavailable_row_count"].eq(1).all()
    not_applicable = proxy[
        ~proxy["model_id"].isin(["B1", "B2", "P0", "P1"])
    ]
    assert not_applicable["status"].eq("not_applicable").all()
    assert not_applicable["evaluation_row_count"].eq(0).all()


def test_e4_rejects_wrong_cohort_and_fabricated_non_success_ordinal_value() -> None:
    indicators = _e4_future_indicators()
    indicators.loc[0, "evaluation_cohort"] = "legacy_development"
    with pytest.raises(
        e4_reference.TrophicReferenceTargetsError, match="location holdout"
    ):
        e4_reference.build_trophic_reference_targets(indicators)

    references = e4_reference.build_trophic_reference_targets(_e4_future_indicators())
    predictions = _e4_predictions()
    row = predictions.index[predictions["ordinal_status"].eq("not_applicable")][0]
    predictions.loc[row, "ordinal_score"] = 0.5
    with pytest.raises(
        e4_evaluation.TrophicStateEvaluationError, match="fabricated values"
    ):
        e4_evaluation.evaluate_trophic_state(predictions, references)


def _e7_predictions() -> pd.DataFrame:
    rows = []
    origin_id = hashlib.sha256(b"e7-origin").hexdigest()
    for horizon in e7.HORIZONS_MONTHS:
        actual = float(horizon % 2)
        for model_id in e7.MODEL_IDS:
            for seed in e7.REGISTERED_SEEDS:
                available = model_id in {"A0", "A1"}
                rows.append(
                    {
                        "model_id": model_id,
                        "seed": seed,
                        "source_id": "wqp",
                        "site_id": "site-1",
                        "common_origin_id": origin_id,
                        "evaluation_cohort": "location_holdout",
                        "evaluation_role": "test",
                        "horizon_months": horizon,
                        "target_year_month": f"2022-{horizon:02d}",
                        "status": "success" if available else "model_unavailable",
                        "y_true": actual,
                        "y_prob": (0.2 + 0.2 * horizon) if available else np.nan,
                    }
                )
    return pd.DataFrame(rows, columns=e7.PREDICTION_COLUMNS)


def test_e7_uses_common_origin_holdout_keys_and_preserves_historical_curve() -> None:
    predictions = e7._normalize_predictions(_e7_predictions())
    availability = {"A0": "available", "P0": "unavailable", "P1": "unavailable", "A1": "available"}
    e7._validate_availability(predictions, availability)
    metrics = e7._metric_rows(predictions, availability)
    pairwise = e7._pairwise_rows(predictions, availability)
    learning = e7._learning_curve(
        pd.DataFrame(
            [
                {"training_rows_per_module": 4096, "status": "completed"},
                {
                    "training_rows_per_module": 16384,
                    "status": "resource_failure_recorded",
                },
            ]
        )
    )

    assert metrics["evaluation_cohort"].eq("location_holdout").all()
    assert metrics["evaluation_role"].eq("test").all()
    assert pairwise["evaluation_cohort"].eq("location_holdout").all()
    assert pairwise["evaluation_role"].eq("test").all()
    status_by_size = learning.set_index("training_rows_per_module")["status"].to_dict()
    assert status_by_size == {4096: "available", 16384: "not_available", 65536: "not_available"}
    assert not learning["saturation_claim_authorized"].any()


def test_e7_rejects_common_origin_time_drift() -> None:
    predictions = _e7_predictions()
    mask = predictions["horizon_months"].eq(3)
    predictions.loc[mask, "target_year_month"] = "2022-04"
    with pytest.raises(e7.ClosureAnfisAblationError, match="time identity"):
        e7._normalize_predictions(predictions)


def test_runner_accepts_exact_e7_unavailable_model_scope() -> None:
    diagnostics = {
        "component_contract_sha256": runner.COMPONENT_CONTRACT_SHA256[
            "E7_anfis_ablation"
        ],
        "input_row_count": 60,
        "available_metric_group_count": 30,
        "unavailable_models": ["P0", "P1"],
        "refit_performed": False,
        "silent_row_deletion": False,
    }

    assert runner._validate_component_diagnostics(
        diagnostics,
        component_id="E7_anfis_ablation",
        status="completed_unavailable",
    ) == diagnostics
    with pytest.raises(runner.ClosureBenchmarkError, match="diagnostics contract"):
        runner._validate_component_diagnostics(
            {**diagnostics, "unavailable_models": ["A2", "P0", "P1"]},
            component_id="E7_anfis_ablation",
            status="completed_unavailable",
        )
