from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest

from src.experiments import evaluate_matched_degradation as e6
from src.experiments import evaluate_planning_inference as e9


def _intents() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    target_months = {
        "2022-01": {1: "2022-02", 2: "2022-03", 3: "2022-04"},
        "2022-02": {1: "2022-03", 2: "2022-04", 3: "2022-05"},
    }
    for index, origin_month in enumerate(("2022-01", "2022-02"), start=1):
        for horizon in (1, 2, 3):
            rows.append(
                {
                    "source_id": "wqp",
                    "site_id": f"site-{index}",
                    "holdout_group_id": f"group-{index}",
                    "common_origin_id": f"origin-{index}",
                    "origin_year_month": origin_month,
                    "target_year_month": target_months[origin_month][horizon],
                    "horizon_months": horizon,
                    "evaluation_cohort": "location_holdout",
                    "evaluation_role": "test",
                    "time_role": "post_2021",
                }
            )
    return pd.DataFrame(rows, columns=list(e6.INTENT_COLUMNS))


def _authority() -> dict[str, object]:
    return {
        "gate": "E0-U",
        "effective_authority": True,
        "sealed_batch_execution_authorized": True,
        "e0_m_authorized": True,
        "e0_u_authorized": True,
        "evaluation_authorized": True,
        "outcome_access_authorized": True,
        "writes_performed": False,
        "sealed_batch_command": "poetry run python -m closure",
    }


def _context(
    *, tables: dict[str, pd.DataFrame], availability: dict[str, str]
) -> dict[str, object]:
    return {
        "execution_id": "test-execution",
        "rng_seed": 1729,
        "tables": tables,
        "stage_results": {},
        "model_availability": availability,
        "software_evidence": {},
    }


def _contract(
    *,
    component_id: str,
    stage_id: str,
    module_name: str,
    source_path: str,
    output_paths: tuple[str, ...],
    availability: dict[str, str],
) -> dict[str, object]:
    return {
        "schema_version": "closure_sealed_evaluation_batch_v1",
        "experiment_id": "closure_v1",
        "formal_model_lock_gate": "E0-M",
        "execution_gate": "E0-U",
        "authority_is_first_execute_operation": True,
        "evaluation_refit": "forbidden",
        "failed_model_replacement": "forbidden",
        "silent_row_deletion": "forbidden",
        "manifest_last": True,
        "one_batch_only": True,
        "sealed_command": "poetry run python -m closure",
        "model_availability": availability,
        "components": [
            {
                "component_id": component_id,
                "stage_id": stage_id,
                "module_name": module_name,
                "source_path": source_path,
                "preflight_api": "preflight_closure_sealed_batch_component",
                "execute_api": "execute_closure_sealed_batch_component",
            }
        ],
        "stages": [
            {
                "stage_id": stage_id,
                "requires_outcomes": True,
                "output_paths": list(output_paths),
            }
        ],
    }


def test_e6_unavailable_retains_exact_78_cell_intent_ledger() -> None:
    availability = {"M0": "available", "P1": "unavailable"}
    result = e6.execute_closure_sealed_batch_component(
        _authority(),
        _contract(
            component_id=e6.COMPONENT_ID,
            stage_id=e6.STAGE_ID,
            module_name="src.experiments.evaluate_matched_degradation",
            source_path="src/experiments/evaluate_matched_degradation.py",
            output_paths=e6.OUTPUT_PATHS,
            availability=availability,
        ),
        _context(tables={e6.INTENT_TABLE: _intents()}, availability=availability),
        Path.cwd(),
    )

    assert result["status"] == "completed_unavailable"
    tables = result["tables"]
    assert tables["degradation_masks"].empty
    assert tables["matched_degradation_metrics"].empty
    assert tables["matched_degradation_pairwise"].empty
    assert tables["robustness_auc"].empty
    failures = tables["failure_registry"]
    assert len(failures) == 78
    assert not failures.duplicated(
        ["scenario_id", "horizon_months", "target_event"]
    ).any()
    assert failures["intent_origin_count"].eq(2).all()
    assert failures["intended_prediction_row_count"].eq(20).all()
    assert failures["available_prediction_row_count"].eq(0).all()
    assert not failures["estimable"].any()
    assert result["diagnostics"]["intent_row_count"] == 6
    assert result["diagnostics"]["common_origin_count"] == 2
    assert result["diagnostics"]["family_b_cell_count"] == 78


def test_e6_fails_closed_if_p1_becomes_available() -> None:
    availability = {"M0": "available", "P1": "available"}
    with pytest.raises(e6.MatchedDegradationError, match="not authorized"):
        e6.execute_closure_sealed_batch_component(
            _authority(),
            _contract(
                component_id=e6.COMPONENT_ID,
                stage_id=e6.STAGE_ID,
                module_name="src.experiments.evaluate_matched_degradation",
                source_path="src/experiments/evaluate_matched_degradation.py",
                output_paths=e6.OUTPUT_PATHS,
                availability=availability,
            ),
            _context(tables={e6.INTENT_TABLE: _intents()}, availability=availability),
            Path.cwd(),
        )


def test_e9_unavailable_preserves_denominators_without_planning_rows() -> None:
    availability = {"P1": "unavailable"}
    result = e9.execute_closure_sealed_batch_component(
        _authority(),
        _contract(
            component_id=e9.COMPONENT_ID,
            stage_id=e9.STAGE_ID,
            module_name="src.experiments.evaluate_planning_inference",
            source_path="src/experiments/evaluate_planning_inference.py",
            output_paths=e9.OUTPUT_PATHS,
            availability=availability,
        ),
        _context(tables={e9.INTENT_TABLE: _intents()}, availability=availability),
        Path.cwd(),
    )

    assert result["status"] == "completed_unavailable"
    tables = result["tables"]
    assert tables["e9_planning_origin_deltas"].empty
    assert tables["e9_planning_bootstrap_replicates"].empty
    inference = tables["e9_planning_inference"]
    failures = tables["e9_planning_failures"]
    sensitivity = tables["e9_planning_sensitivity"]
    coherence = tables["e9_ecological_coherence"]
    assert len(inference) == 9
    assert inference["row_count"].eq(6).all()
    assert inference["cluster_count"].eq(2).all()
    assert inference["status"].eq("model_unavailable").all()
    assert inference[["estimate", "ci95_lower", "ci95_upper", "p_holm"]].isna().all().all()
    assert len(failures) == 27
    assert failures["intent_origin_count"].eq(2).all()
    assert failures["intended_scenario_row_count"].eq(10).all()
    assert not failures["estimable"].any()
    assert len(sensitivity) == 81
    assert sensitivity["row_count"].eq(6).all()
    assert len(coherence) == 9
    assert coherence["row_count"].eq(6).all()
    assert coherence["dictamen"].eq(
        "not_estimable_model_or_rows_unavailable"
    ).all()
    assert result["diagnostics"]["intent_row_count"] == 6
    assert result["diagnostics"]["intended_action_seed_row_count"] == 270
    assert result["diagnostics"]["holm_universe_size"] == 9


def test_e9_fails_closed_if_p1_becomes_available() -> None:
    availability = {"P1": "available"}
    with pytest.raises(e9.ClosurePlanningInferenceError, match="not authorized"):
        e9.execute_closure_sealed_batch_component(
            _authority(),
            _contract(
                component_id=e9.COMPONENT_ID,
                stage_id=e9.STAGE_ID,
                module_name="src.experiments.evaluate_planning_inference",
                source_path="src/experiments/evaluate_planning_inference.py",
                output_paths=e9.OUTPUT_PATHS,
                availability=availability,
            ),
            _context(tables={e9.INTENT_TABLE: _intents()}, availability=availability),
            Path.cwd(),
        )


@pytest.mark.parametrize(
    "normalizer",
    [e6._normalize_unavailable_intents, e9._normalize_unavailable_intents],
)
def test_unavailable_branch_rejects_incomplete_horizon_universe(
    normalizer: Callable[[pd.DataFrame], pd.DataFrame],
) -> None:
    intents = _intents()
    intents = intents[intents["horizon_months"].ne(3)].reset_index(drop=True)
    with pytest.raises(Exception, match="horizon"):
        normalizer(intents)
