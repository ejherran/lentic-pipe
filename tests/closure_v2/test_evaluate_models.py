from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.experiments.closure_v2 import evaluate_models as evaluation


def test_parser_keeps_execute_and_finalize_separate() -> None:
    parser = evaluation.build_parser()
    assert parser.parse_args([]).execute is False
    assert parser.parse_args(["--execute"]).execute is True
    assert parser.parse_args(["--finalize"]).finalize is True
    assert parser.parse_args(["--repair-failed-values"]).repair_failed_values is True
    with pytest.raises(SystemExit):
        parser.parse_args(["--execute", "--finalize"])


def test_family_requires_all_five_registered_seeds() -> None:
    scores = {}
    for model in ("P0", "P1", "B2", "A1", "B1"):
        for seed in evaluation.EXPECTED_SEEDS:
            slot = evaluation._empty_score(2)
            slot["valid"][:] = True
            slot["bloom"][:] = 0.2
            slot["risk"][:] = 0.3
            slot["threshold"][:] = 0.4
            scores[(model, seed)] = slot
    scores[("P1", evaluation.EXPECTED_SEEDS[-1])]["valid"][0, 0] = False
    family = evaluation._family_scores(scores)
    assert family[("P0", -1)]["valid"].all()
    assert not family[("P1", -1)]["valid"][0, 0]
    assert family[("P1", -1)]["valid"][1, 0]


def test_ece_is_zero_for_exact_two_bin_predictions() -> None:
    y = np.asarray([0, 0, 1, 1])
    p = np.asarray([0.0, 0.0, 1.0, 1.0])
    assert evaluation._ece(y, p, np.ones(4)) == 0.0


def test_expert_delta_is_zero_across_calendar_gap() -> None:
    frame = pd.DataFrame({
        "source_id": ["wqp", "wqp"], "site_id": ["s", "s"],
        "year_month": ["2020-01", "2020-03"], "row_present": [True, True],
        "mean_TP_ugL": [10.0, 100.0], "mean_TN_ugL": [300.0, 1500.0],
        "TN_TP_ratio": [30.0, 30.0], "mean_DO_mgL": [8.0, 8.0],
        "mean_pH": [7.5, 7.5], "mean_turbidity_NTU": [5.0, 5.0],
        "mean_secchi_depth_m": [3.0, 3.0], "mean_temperature_C": [22.0, 30.0],
    })
    states = evaluation._expert_states(frame)
    assert states.loc[1, "delta_yN"] == 0.0
    assert states.loc[1, "delta_yF"] == 0.0
    assert states.loc[1, "delta_yT"] == 0.0


def test_output_contract_has_required_denominators_and_statuses() -> None:
    required = {
        "intent_to_predict", "input_eligible", "prediction_status", "failure_reason",
        "target_available", "metric_evaluable", "shared_success",
    }
    assert required.issubset(evaluation.PREDICTION_COLUMNS)
    assert evaluation.SENSITIVITY_CUTOFFS == (25.0, 30.0, 33.0, 50.0)


def test_exclusive_bundle_refuses_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "x.csv"
    target.write_bytes(b"old")
    with pytest.raises(evaluation.EvaluationError, match="overwrite"):
        evaluation._exclusive_bundle([(Path("x.csv"), b"new")], root=tmp_path)
    assert target.read_bytes() == b"old"
