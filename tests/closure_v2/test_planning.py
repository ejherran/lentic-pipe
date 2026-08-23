from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.experiments.closure_v2 import run_planning as planning


def _origins() -> pd.DataFrame:
    return pd.DataFrame({
        "source_id": ["wqp", "wqp"], "site_id": ["a", "b"],
        "mean_TP_ugL": [100.0, np.nan], "mean_TN_ugL": [1000.0, 1000.0],
        "mean_secchi_depth_m": [1.0, 1.0], "mean_turbidity_NTU": [10.0, 10.0],
        "mean_DO_mgL": [8.0, 8.0], "log_TP": [0.0, np.nan], "log_TN": [0.0, 0.0],
        "TN_TP_ratio": [10.0, np.nan],
    })


def test_parser_separates_execute_and_finalize() -> None:
    parser = planning.build_parser()
    assert parser.parse_args([]).execute is False
    assert parser.parse_args(["--execute"]).execute is True
    assert parser.parse_args(["--finalize"]).finalize is True
    with pytest.raises(SystemExit):
        parser.parse_args(["--execute", "--finalize"])


def test_locked_action_universe_is_exact() -> None:
    assert planning.ACTION_SCENARIOS == (
        "tp_reduction_10", "tp_reduction_25", "tn_reduction_10", "tp_tn_reduction_10",
        "clarity_mild", "clarity_strong", "oxygen_support_05",
        "nutrient_clarity_mild", "nutrient_clarity_strong",
    )
    assert planning.BOOTSTRAP_REPLICATES == 2000


def test_apply_scenario_preserves_missing_action_input() -> None:
    scenario = planning.Scenario(
        "tp_reduction_10", "nutrient_reduction_tp", 1.0,
        (planning.Operation("TP_ugL", "mean_TP_ugL", "multiply", 0.9),),
    )
    support = {column: (0.0, 5000.0) for column in planning.ACTION_COLUMNS}
    modified, available, violation, clipped = planning.apply_scenario(
        _origins(), scenario, support, {"TP_ugL": (0.0, 5000.0)},
    )
    assert modified.loc[0, "mean_TP_ugL"] == 90.0
    assert available.tolist() == [True, False]
    assert not violation.any()
    assert not clipped.any()
    assert modified.loc[0, "TN_TP_ratio"] == pytest.approx(1000.0 / 90.0)


def test_apply_scenario_records_support_and_plausible_clipping() -> None:
    scenario = planning.Scenario(
        "oxygen_support_05", "oxygen_support_proxy", 0.6,
        (planning.Operation("DO_mgL", "mean_DO_mgL", "add", 100.0),),
    )
    support = {column: (0.0, 12.0) for column in planning.ACTION_COLUMNS}
    modified, available, violation, clipped = planning.apply_scenario(
        _origins(), scenario, support, {"DO_mgL": (0.0, 20.0)},
    )
    assert available.all()
    assert violation.all()
    assert clipped.all()
    assert modified["mean_DO_mgL"].eq(20.0).all()


def test_irc_and_bloom_proxy_follow_locked_formula() -> None:
    state = np.asarray([[0.9, 0.3, 0.6, 0, 0, 0, 0, 0, 0]], dtype=float)
    irc = planning._irc(state)
    bloom = planning._bloom_proxy(state, irc)
    assert irc[0] == pytest.approx((0.9 + 0.7 + 0.6) / 3)
    assert bloom[0] == pytest.approx(0.5 * 0.6 + 0.5 * irc[0])


def test_holm_family_helper_rejects_reduced_universe() -> None:
    from src.experiments.evaluate_planning_inference import holm_adjust

    with pytest.raises(Exception, match="exact nine actions"):
        holm_adjust({"tp_reduction_10": 0.01})


def test_exclusive_bundle_refuses_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "x.csv"
    target.write_bytes(b"old")
    with pytest.raises(planning.PlanningError, match="overwrite"):
        planning._exclusive_bundle([(Path("x.csv"), b"new")], root=tmp_path)
    assert target.read_bytes() == b"old"
