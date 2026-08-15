from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.experiments import closure_phase3_context as phase3_context
from src.experiments import compare_models_clustered as e5
from src.experiments import evaluate_site_transfer as e2
from src.experiments import evaluate_threshold_sensitivity as e3
from src.experiments import run_closure_benchmark as runner


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _authority() -> dict[str, Any]:
    return {
        "gate": "E0-U",
        "effective_authority": True,
        "sealed_batch_execution_authorized": True,
        "e0_m_authorized": True,
        "e0_u_authorized": True,
        "evaluation_authorized": True,
        "outcome_access_authorized": True,
        "writes_performed": False,
        "sealed_batch_command": runner.SEALED_BATCH_COMMAND,
    }


def _prediction_surface() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    model_status = {
        "B1": "success",
        "B2": "success",
        "P0": "model_unavailable",
        "P1": "model_unavailable",
        "M0": "success",
    }
    for origin_index, (common_origin_id, chla) in enumerate(
        (("a" * 64, 20.0), ("b" * 64, 40.0)),
        start=1,
    ):
        for model_id, status in model_status.items():
            successful = status == "success"
            rows.append(
                {
                    "source_id": "wqp",
                    "site_id": "site-1",
                    "common_origin_id": common_origin_id,
                    "horizon_months": 1,
                    "model_id": model_id,
                    "model_seed": 1729,
                    "seed_slot": 1729,
                    "evaluation_cohort": "location_holdout",
                    "evaluation_role": "test",
                    "terminal_status": status,
                    "bloom_status": status,
                    "bloom_probability": (
                        0.2 + 0.5 * (origin_index - 1) if successful else np.nan
                    ),
                    "actual_bloom": float(chla > 30.0),
                    "alert_threshold": 0.5 if successful else np.nan,
                    "actual_chla_ug_l": chla,
                }
            )
    return pd.DataFrame(rows)


def _batch_context(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    return {
        "execution_id": "phase3-synthetic-contract-test",
        "rng_seed": 1729,
        "tables": tables,
        "stage_results": {},
        "model_availability": dict(runner.CURRENT_MODEL_AVAILABILITY),
        "software_evidence": {},
    }


def test_e1_comparisons_recompute_on_exact_shared_success_rows() -> None:
    columns = list(runner.PAIRED_METRIC_COLUMNS)
    records: list[dict[str, Any]] = []
    values = {
        "P1": (("o1", 0.1), ("o2", 0.2)),
        "B1": (("o2", 0.4), ("o3", 0.5)),
    }
    for model_id, origins in values.items():
        for origin, loss in origins:
            records.append(
                {
                    "source_id": "wqp",
                    "site_id": "site-1",
                    "holdout_group_id": "wqp::site-1",
                    "common_origin_id": origin,
                    "horizon_months": 1,
                    "model_id": model_id,
                    "model_seed": 1729,
                    "seed_slot": 1729,
                    "evaluation_cohort": "location_holdout",
                    "metric": "brier_loss",
                    "loss": loss,
                    "terminal_status": "success",
                }
            )
    paired = pd.DataFrame(records, columns=columns)

    comparisons = runner._e1_comparisons(paired)

    row = comparisons.loc[
        comparisons["comparison_id"].eq("P1_vs_B1")
        & comparisons["metric"].eq("brier_loss")
    ].iloc[0]
    assert row["paired_origin_count"] == 1
    assert row["mean_loss_model_a"] == 0.2
    assert row["mean_loss_model_b"] == 0.4
    assert np.isclose(row["mean_loss_difference_a_minus_b"], -0.2)
    assert row["terminal_status"] == "estimated"


def test_e2_executes_holdout_only_and_preserves_unavailable_designs() -> None:
    predictions = _prediction_surface()
    strata = pd.DataFrame(
        [
            {
                "source_id": "wqp",
                "site_id": "site-1",
                "series_length_band": "long",
                "historical_bloom_present": "true",
                "coverage_band": "high",
            }
        ]
    )

    result = e2.execute_closure_sealed_batch_component(
        _authority(),
        runner.sealed_batch_contract(),
        _batch_context({"predictions_long": predictions, "e2_site_strata": strata}),
        PROJECT_ROOT,
    )

    assert result["status"] == "completed_unavailable"
    assert result["diagnostics"]["e2a_complete"] is True
    assert result["diagnostics"]["legacy_surface_available"] is False
    assert result["diagnostics"]["e2b_predictions_available"] is False
    gaps = result["tables"]["e2_generalization_gaps"]
    assert not gaps.empty
    assert gaps["estimable"].eq(False).all()  # noqa: E712
    assert gaps["legacy_value"].isna().all()
    assert gaps["not_estimable_reason"].eq(
        "legacy_evaluation_surface_not_frozen_before_e0_u"
    ).all()
    metrics = result["tables"]["e2_location_metrics"]
    unavailable = metrics["model_id"].isin(["P0", "P1"])
    assert metrics.loc[unavailable, "terminal_status"].eq("model_unavailable").all()
    assert metrics.loc[unavailable, "event_count"].eq(2).all()
    assert metrics.loc[unavailable, "successful_event_count"].eq(0).all()


def test_e2_rejects_postlock_grouped_predictions() -> None:
    predictions = _prediction_surface()
    strata = pd.DataFrame(
        [["wqp", "site-1", "long", "true", "high"]],
        columns=e2.SITE_STRATA_COLUMNS,
    )
    tables = {
        "predictions_long": predictions,
        "e2_site_strata": strata,
        "e2_grouped_predictions": predictions.assign(fold_id=1),
    }

    try:
        e2.execute_closure_sealed_batch_component(
            _authority(),
            runner.sealed_batch_contract(),
            _batch_context(tables),
            PROJECT_ROOT,
        )
    except e2.ClosureSiteTransferError as exc:
        assert "not frozen before E0-U" in str(exc)
    else:
        raise AssertionError("E2 accepted a post-lock grouped prediction surface")


def test_e3_executes_fixed_threshold_sensitivity_without_refit() -> None:
    result = e3.execute_closure_sealed_batch_component(
        _authority(),
        runner.sealed_batch_contract(),
        _batch_context({"predictions_long": _prediction_surface()}),
        PROJECT_ROOT,
    )

    assert result["status"] == "completed_unavailable"
    assert result["diagnostics"]["thresholds_ug_l"] == [25.0, 30.0, 33.0, 50.0]
    assert result["diagnostics"]["model_scores_refit"] is False
    assert result["diagnostics"]["calibrator_fit_performed"] is False
    assert result["diagnostics"]["decision_threshold_selection_performed"] is False
    prevalence = result["tables"]["e3_threshold_prevalence"]
    assert set(prevalence["threshold_ug_l"]) == {25.0, 30.0, 33.0, 50.0}
    metrics = result["tables"]["e3_threshold_metrics"]
    unavailable = metrics["model_id"].isin(["P0", "P1"])
    assert metrics.loc[unavailable, "terminal_status"].eq("model_unavailable").all()
    assert metrics.loc[unavailable, "origin_count"].eq(2).all()


def test_e3_pairwise_helper_uses_only_intersection() -> None:
    metric_rows = pd.DataFrame(
        [
            {
                "threshold_ug_l": 30.0,
                "horizon_months": 1,
                "evaluation_cohort": "location_holdout",
                "model_id": model_id,
                "seed_slot": 1729,
            }
            for model_id in ("P1", "B1")
        ]
    )
    scored_rows: list[dict[str, Any]] = []
    for model_id, values in {
        "P1": (("o1", 0, 0.1), ("o2", 1, 0.8)),
        "B1": (("o2", 1, 0.6), ("o3", 0, 0.4)),
    }.items():
        for origin, label, probability in values:
            scored_rows.append(
                {
                    "source_id": "wqp",
                    "site_id": "site-1",
                    "common_origin_id": origin,
                    "horizon_months": 1,
                    "model_id": model_id,
                    "model_seed": 1729,
                    "seed_slot": 1729,
                    "evaluation_cohort": "location_holdout",
                    "threshold_ug_l": 30.0,
                    "actual_bloom": label,
                    "fixed_probability": probability,
                    "decision_threshold": 0.5,
                    "alert": int(probability >= 0.5),
                }
            )
    pairwise = e3._pairwise_differences(metric_rows, pd.DataFrame(scored_rows))
    brier = pairwise.loc[
        pairwise["left_model_id"].eq("P1")
        & pairwise["right_model_id"].eq("B1")
        & pairwise["metric"].eq("brier")
    ].iloc[0]
    assert brier["paired_origin_count"] == 1
    assert np.isclose(brier["left_value"], (0.8 - 1.0) ** 2)
    assert np.isclose(brier["right_value"], (0.6 - 1.0) ** 2)
    assert np.isclose(brier["difference_left_minus_right"], -0.12)


def test_e3_source_contains_no_fit_or_threshold_selection_api() -> None:
    tree = ast.parse(
        Path("src/experiments/evaluate_threshold_sensitivity.py").read_text(
            encoding="utf-8"
        )
    )
    functions = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert "_fit_calibrator" not in functions
    assert "LogisticRegression" not in ast.unparse(tree)
    assert not any(name.startswith("sklearn.linear_model") for name in imports)


def test_e5_preserves_exact_27_row_holm_ledger_with_denominators() -> None:
    registry = phase3_context._load_hypothesis_registry(PROJECT_ROOT)
    paired = pd.DataFrame(
        [
            {
                "source_id": "wqp",
                "site_id": "site-1",
                "holdout_group_id": "wqp::site-1",
                "common_origin_id": "a" * 64,
                "horizon_months": 1,
                "model_id": "B1",
                "model_seed": 1729,
                "seed_slot": 1729,
                "evaluation_cohort": "location_holdout",
                "metric": "brier_loss",
                "loss": 0.1,
                "terminal_status": "success",
            },
            {
                "source_id": "wqp",
                "site_id": "site-1",
                "holdout_group_id": "wqp::site-1",
                "common_origin_id": "a" * 64,
                "horizon_months": 1,
                "model_id": "P1",
                "model_seed": 1729,
                "seed_slot": 1729,
                "evaluation_cohort": "location_holdout",
                "metric": "brier_loss",
                "loss": np.nan,
                "terminal_status": "model_unavailable",
            },
        ],
        columns=e5.INPUT_COLUMNS,
    )

    result = e5.execute_closure_sealed_batch_component(
        _authority(),
        runner.sealed_batch_contract(),
        _batch_context(
            {"paired_metric_rows": paired, "hypothesis_registry": registry}
        ),
        PROJECT_ROOT,
    )

    assert result["status"] == "completed_unavailable"
    effects = result["tables"]["pairwise_effects"]
    assert len(effects) == 27
    assert effects["multiplicity_family"].value_counts().to_dict() == e5.FAMILY_COUNTS
    assert effects.groupby("multiplicity_family")[
        "multiplicity_universe_size"
    ].first().to_dict() == e5.FAMILY_UNIVERSES
    assert effects["intent_origin_count"].eq(1).all()
    assert effects["intent_site_count"].eq(1).all()
    assert effects["shared_success_origin_count"].eq(0).all()
    assert effects["raw_p_value"].isna().all()
    assert effects["holm_p_value"].isna().all()
    assert effects["effect_estimate_numeric"].isna().all()
    assert result["tables"]["site_level_losses"].empty
    assert result["tables"]["bootstrap_distributions"].empty
    assert runner._validate_component_diagnostics(
        result["diagnostics"],
        component_id="E5_clustered_inference",
        status=result["status"],
    ) == result["diagnostics"]
