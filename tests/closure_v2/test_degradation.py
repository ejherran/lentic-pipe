from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.experiments.closure_v2 import run_degradation as degradation


def _raw() -> pd.DataFrame:
    rows = []
    for month in pd.period_range("2020-01", "2020-08", freq="M"):
        for variable in degradation.RAW_VARIABLES:
            rows.append({
                "evaluation_cohort": "fresh_primary", "source_id": "wqp", "site_id": "s",
                "year_month": str(month), "row_present": True, "raw_variable": variable,
                "value": 1.0, "eligible": True,
            })
    return pd.DataFrame(rows)


def test_parser_separates_execute_and_finalize() -> None:
    parser = degradation.build_parser()
    assert parser.parse_args([]).execute is False
    assert parser.parse_args(["--execute"]).execute is True
    assert parser.parse_args(["--finalize"]).finalize is True
    with pytest.raises(SystemExit):
        parser.parse_args(["--execute", "--finalize"])


def test_scenarios_cover_every_guide_category() -> None:
    assert set(degradation.SCENARIOS) == {
        "control", "mcar_10", "mcar_25", "mcar_50",
        "block_1m_10", "block_3m_10", "block_6m_25",
        "ablate_nutrients", "ablate_clarity", "ablate_oxygen", "combined_severe",
    }
    assert len(degradation.EXPECTED_SEEDS) == 5


def test_hash_masks_are_deterministic_and_namespaced() -> None:
    raw = _raw()
    first = degradation._mcar_mask(raw, "mcar_25", 1729, 0.25)
    second = degradation._mcar_mask(raw.copy(), "mcar_25", 1729, 0.25)
    assert first.equals(second)
    assert degradation._payload("mcar_25", 1729, "wqp", "s", "2020-01", "mean_TP_ugL").startswith(b'["closure_v2","P15"')


def test_ablations_only_mask_eligible_registered_variables() -> None:
    raw = _raw()
    raw.loc[raw["raw_variable"].eq("mean_TP_ugL").idxmax(), "eligible"] = False
    nutrient = degradation._scenario_mask(raw, "ablate_nutrients", 1729)
    assert not nutrient.loc[raw["raw_variable"].eq("mean_TP_ugL").idxmax()]
    assert set(raw.loc[nutrient, "raw_variable"]) == {"mean_TP_ugL", "mean_TN_ugL"}
    oxygen = degradation._scenario_mask(raw, "ablate_oxygen", 1729)
    assert set(raw.loc[oxygen, "raw_variable"]) == {"mean_DO_mgL"}


def test_block_mask_is_deterministic_and_contiguous() -> None:
    raw = _raw()
    first = degradation._block_mask(raw, "block_3m_10", 1729, 3, 0.10)
    second = degradation._block_mask(raw.copy(), "block_3m_10", 1729, 3, 0.10)
    assert first.equals(second)
    for _, group in raw.loc[first].groupby("raw_variable"):
        periods = sorted(pd.PeriodIndex(group["year_month"], freq="M"))
        assert len(periods) == 3
        assert periods[-1].ordinal - periods[0].ordinal == 2


def test_f2_uses_weights_and_never_encodes_absence_as_zero() -> None:
    y = np.asarray([1, 1, 0, 0])
    predicted = np.asarray([1, 0, 1, 0])
    assert degradation._f2(y, predicted, np.ones(4)) == pytest.approx(5 / 10)
    assert np.isnan(degradation._f2(np.zeros(2), np.zeros(2), np.ones(2)))


def test_m0_interval_metrics_are_explicitly_not_applicable() -> None:
    frame = pd.DataFrame({
        "metric_evaluable": [True], "outcome_bloom_30": [True],
        "bloom_probability": [0.7], "predicted_alert": [True],
        "prediction_successful": [True], "source_id": ["wqp"], "site_id": ["s"],
        "origin_id": ["o"], "risk_interval_lower_90": [np.nan],
        "risk_interval_upper_90": [np.nan], "target_risk_chla_h": [0.5],
    })
    values = degradation._metric_values(frame, "observation_weighted", "M0")
    for metric in ("picp", "mpiw", "winkler"):
        assert np.isnan(values[metric][0])
        assert values[metric][1] == "not_applicable_distinct_type2_interval_semantics"


def test_exclusive_bundle_refuses_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "x.csv"
    target.write_bytes(b"old")
    with pytest.raises(degradation.DegradationError, match="overwrite"):
        degradation._exclusive_bundle([(Path("x.csv"), b"new")], root=tmp_path)
    assert target.read_bytes() == b"old"
