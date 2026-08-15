from __future__ import annotations

import hashlib
import math

import numpy as np
import pandas as pd
import pytest

from src.experiments import calibrate_uncertainty_closure as e8


def _locked_factors() -> pd.DataFrame:
    rows = []
    for model_id in e8.UNCERTAINTY_MODEL_IDS:
        for seed in e8.REGISTERED_SEEDS:
            for horizon in e8.HORIZONS_MONTHS:
                for nominal in e8.NOMINAL_LEVELS:
                    rows.append(
                        {
                            "model_id": model_id,
                            "model_seed": seed,
                            "horizon_months": horizon,
                            "coverage_level": nominal,
                            "calibration_year": 2021,
                            "finite_rows": 224,
                            "order_statistic_rank": min(
                                224, math.ceil(225 * nominal)
                            ),
                            "q_c": e8.GAUSSIAN_FACTORS[nominal] + 0.1,
                            "status": "completed",
                        }
                    )
    return pd.DataFrame(rows, columns=e8.LOCKED_FACTOR_COLUMNS)


def _evaluation(rows_per_group: int = 30) -> pd.DataFrame:
    rows = []
    for origin_index in range(rows_per_group):
        common_origin_id = hashlib.sha256(
            f"e8-origin-{origin_index}".encode()
        ).hexdigest()
        for horizon in e8.HORIZONS_MONTHS:
            actual = 0.2 + 0.1 * horizon + 0.001 * origin_index
            for model_id in e8.UNCERTAINTY_MODEL_IDS:
                for seed in e8.REGISTERED_SEEDS:
                    prediction = actual + (0.01 if model_id == "A1" else -0.01)
                    rows.append(
                        {
                            "source_id": "wqp",
                            "site_id": f"site-{origin_index % 5}",
                            "holdout_group_id": f"holdout-{origin_index % 3}",
                            "common_origin_id": common_origin_id,
                            "origin_year_month": "2021-12",
                            "target_year_month": f"2022-{horizon:02d}",
                            "horizon_months": horizon,
                            "evaluation_cohort": "location_holdout",
                            "evaluation_role": "test",
                            "model_id": model_id,
                            "model_seed": seed,
                            "seed_slot": seed,
                            "status": "success",
                            "y_true": actual,
                            "prediction": prediction,
                            "sigma": 0.1,
                            "nutrient_evidence_quartile": f"q{origin_index % 4 + 1}",
                            "input_missingness_quartile": f"q{origin_index % 4 + 1}",
                            "location_input_frequency": (
                                "infrequent_le_median"
                                if origin_index % 2 == 0
                                else "frequent_gt_median"
                            ),
                            "location_novelty": "heldout_unseen",
                            "degradation_scenario": "control",
                        }
                    )
    return pd.DataFrame(
        rows,
        columns=[*e8.EVALUATION_COLUMNS, *e8.OPTIONAL_STRATUM_COLUMNS],
    )


def test_e8_consumes_exact90_locked_factors_without_refitting() -> None:
    factors = e8.normalize_locked_conformal_factors(_locked_factors())
    evaluation = e8._normalize_evaluation(_evaluation())
    applied = e8.apply_locked_conformal_factors(evaluation, factors)

    assert len(factors) == 90
    assert set(applied["model_id"]) == {"A0", "A1"}
    assert "A2" not in set(applied["model_id"])
    row = applied.iloc[0]
    raw_half_width = (row["raw_upper"] - row["raw_lower"]) / 2.0
    locked_half_width = (row["locked_upper"] - row["locked_lower"]) / 2.0
    assert raw_half_width == pytest.approx(
        e8.GAUSSIAN_FACTORS[float(row["nominal_coverage"])] * row["sigma"]
    )
    assert locked_half_width == pytest.approx(row["q_c"] * row["sigma"])
    assert e8.COMPONENT_CONTRACT["calibration_table"] == "forbidden"
    assert not hasattr(e8, "fit_conformal_factors")


def test_e8_retains_denominators_conditionals_winkler_and_family_e() -> None:
    factors = e8.normalize_locked_conformal_factors(_locked_factors())
    evaluation = e8._normalize_evaluation(_evaluation())
    applied = e8.apply_locked_conformal_factors(evaluation, factors)
    ledger, comparison = e8._summary_rows(applied)
    conditional = e8._conditional_rows(applied)

    assert len(ledger) == 180
    assert ledger["attempted_row_count"].eq(30).all()
    assert ledger["success_row_count"].eq(30).all()
    assert ledger["interval_row_count"].eq(30).all()
    assert ledger["winkler_interval_score"].notna().all()
    assert set(conditional["breakdown_id"]) == {
        "global",
        "horizon",
        "predicted_risk_band",
        *e8.OPTIONAL_STRATUM_COLUMNS,
    }
    global_rows = conditional[conditional["breakdown_id"].eq("global")]
    assert global_rows["status"].eq("available").all()
    assert global_rows["winkler_interval_score"].notna().all()
    horizon_rows = conditional[conditional["breakdown_id"].eq("horizon")]
    assert horizon_rows["status"].eq("available").all()
    assert horizon_rows["winkler_interval_score"].notna().all()

    confirmatory = comparison[comparison["analysis_role"].eq("confirmatory")]
    assert len(confirmatory) == 1
    assert confirmatory.iloc[0]["hypothesis_id"] == (
        "H_E_uncertainty_before_vs_after_recalibration"
    )
    assert confirmatory.iloc[0]["model_id"] == "P1"
    assert confirmatory.iloc[0]["status"] == "not_estimable_model_unavailable"
    assert confirmatory.iloc[0]["holm_family_size"] == 1
    assert confirmatory.iloc[0][
        ["effect_estimate", "ci_lower", "ci_upper", "p_value"]
    ].isna().all()


def test_e8_rejects_factor_or_evaluation_scope_drift() -> None:
    factors = _locked_factors().iloc[:-1].copy()
    with pytest.raises(e8.ClosureUncertaintyError, match="exact90"):
        e8.normalize_locked_conformal_factors(factors)

    evaluation = _evaluation(rows_per_group=1)
    evaluation.loc[0, "evaluation_cohort"] = "legacy_development"
    with pytest.raises(e8.ClosureUncertaintyError, match="locked scope"):
        e8._normalize_evaluation(evaluation)


def test_e8_non_success_rows_keep_failure_denominators_without_intervals() -> None:
    factors = e8.normalize_locked_conformal_factors(_locked_factors())
    evaluation = _evaluation(rows_per_group=1)
    mask = evaluation["model_id"].eq("A0") & evaluation["seed_slot"].eq(1729)
    evaluation.loc[mask, "status"] = "input_ineligible"
    evaluation.loc[mask, ["prediction", "sigma"]] = np.nan
    normalized = e8._normalize_evaluation(evaluation)
    applied = e8.apply_locked_conformal_factors(normalized, factors)
    ledger, _ = e8._summary_rows(applied)
    failed = ledger[
        ledger["model_id"].eq("A0")
        & ledger["seed_slot"].eq(1729)
    ]
    assert failed["attempted_row_count"].eq(1).all()
    assert failed["success_row_count"].eq(0).all()
    assert failed["input_ineligible_row_count"].eq(1).all()
    assert failed["interval_row_count"].eq(0).all()
    assert failed["winkler_interval_score"].isna().all()
