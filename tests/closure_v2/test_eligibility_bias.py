from __future__ import annotations

import numpy as np
import pandas as pd

from src.experiments.closure_v2 import audit_eligibility_bias


def _bias_frame() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for index in range(40):
        eligible = index < 32
        role = "training" if index < 30 else "model_selection"
        row: dict[str, object] = {
            "model_id": "P0",
            "base_seed": 1729,
            "source_id": "wqp",
            "site_id": f"wqp:{index % 8}",
            "origin_year_month": "2018-01" if role == "training" else "2019-01",
            "target_year_month": "2018-02" if role == "training" else "2019-02",
            "time_role": role,
            "intent_to_fit": True,
            "complete_case_eligible": eligible,
            "origin_year": 2018 if role == "training" else 2019,
            "origin_month": 1,
            "climatic_season": "DJF",
            "precursor_coverage_fraction": (
                0.90 + 0.01 * (index % 4) if eligible else 0.65 + 0.01 * (index % 4)
            ),
            "precursor_coverage_band": "high" if eligible else "medium",
            "series_length_months": 100 + index,
            "series_length_band": "long",
            "historical_bloom_presence": index % 2 == 0,
            "delta_previous_month_missing": False,
            "input_missing_channel_count": 0 if eligible else 13,
            "target_missing_count": 0 if eligible else 9,
            "site_noneligible_fraction": 0.2,
        }
        for offset, name in enumerate(audit_eligibility_bias.STATE_NAMES):
            row[f"origin_{name}"] = float(index + offset) / 10.0
        rows.append(row)
    return pd.DataFrame(rows)


def test_numeric_smd_alerts_on_large_coverage_difference() -> None:
    row = audit_eligibility_bias._numeric_balance(
        _bias_frame(),
        variable="precursor_coverage_fraction",
        model_id="P0",
        seed=1729,
        scope="fit_intent",
    )
    assert row["alert"] is True
    assert float(row["abs_smd"]) > 0.20


def test_complete_separation_is_an_alert_not_zero() -> None:
    row = audit_eligibility_bias._numeric_balance(
        _bias_frame(),
        variable="input_missing_channel_count",
        model_id="P0",
        seed=1729,
        scope="fit_intent",
    )
    assert row["effect_state"] == "complete_separation"
    assert row["alert"] is True
    assert np.isnan(row["smd"])


def test_categorical_balance_reports_every_level() -> None:
    rows = audit_eligibility_bias._categorical_balance(
        _bias_frame(),
        variable="precursor_coverage_band",
        model_id="P0",
        seed=1729,
        scope="fit_intent",
    )
    assert {row["level"] for row in rows} == {"high", "medium"}
    assert all(row["alert"] for row in rows)


def test_selection_diagnostic_is_deterministic_and_converges() -> None:
    frame = _bias_frame()
    first = audit_eligibility_bias.fit_selection_diagnostic(frame, model_id="P0", seed=1729)
    second = audit_eligibility_bias.fit_selection_diagnostic(
        frame.sample(frac=1.0, random_state=11), model_id="P0", seed=1729
    )
    by_name_first = {row["predictor"]: row for row in first}
    by_name_second = {row["predictor"]: row for row in second}
    assert by_name_first.keys() == by_name_second.keys()
    assert all(row["converged"] for row in first)
    for predictor in by_name_first:
        assert np.isclose(
            by_name_first[predictor]["coefficient_log_odds"],
            by_name_second[predictor]["coefficient_log_odds"],
        )


def test_month_counts_retain_noneligible_rows() -> None:
    counts = audit_eligibility_bias.build_month_counts(_bias_frame())
    assert counts["intent_rows"].sum() == 40
    assert counts["noneligible_rows"].sum() == 8
