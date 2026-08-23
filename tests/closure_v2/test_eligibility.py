from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from src.experiments.closure_contract import ClosureContractError
from src.experiments.closure_v2 import build_eligibility
from src.experiments.closure_v2.contracts import validate_eligibility_policy


def _sequence_row(*, role: str = "training", status: str = "success") -> dict[str, object]:
    origin, target = {
        "training": ("2018-10", "2018-11"),
        "model_selection": ("2019-10", "2019-11"),
        "calibration_threshold": ("2021-10", "2021-11"),
    }[role]
    row: dict[str, object] = {
        "source_id": "wqp",
        "site_id": "wqp:test",
        "origin_year_month": origin,
        "target_year_month": target,
        "model_id": "P0",
        "base_seed": np.nan,
        "assignment_role": "development",
        "time_role": role,
        "sequence_status": status,
        "failure_reason": "" if status == "success" else "missing_target_state",
    }
    for column in build_eligibility.INPUT_COLUMNS:
        row[column] = np.arange(12, dtype=np.float32)
    for column in build_eligibility.TARGET_COLUMNS:
        row[column] = np.float32(1.0)
    if status != "success":
        for column in (*build_eligibility.INPUT_COLUMNS, *build_eligibility.TARGET_COLUMNS):
            row[column] = None
    return row


def test_incomplete_row_is_retained_without_invalidating_complete_rows() -> None:
    rows = [_sequence_row(), _sequence_row(status="autoregressive_target_unavailable")]
    rows[1]["origin_year_month"] = "2018-08"
    rows[1]["target_year_month"] = "2018-09"
    classified = build_eligibility.classify_sequence_frame(
        pd.DataFrame(rows), model_id="P0", base_seed=1729, holdout_keys=set()
    )
    assert len(classified) == 2
    assert classified["fit_eligible"].tolist() == [True, False]
    assert classified.loc[1, "sequence_status"] == "autoregressive_target_unavailable"
    assert "input_incomplete" in classified.loc[1, "exclusion_reason"]


def test_calibration_complete_case_is_reserved_not_silently_dropped() -> None:
    classified = build_eligibility.classify_sequence_frame(
        pd.DataFrame([_sequence_row(role="calibration_threshold")]),
        model_id="P0",
        base_seed=1729,
        holdout_keys=set(),
    )
    assert classified.loc[0, "fit_eligible"] == False  # noqa: E712
    assert classified.loc[0, "calibration_eligible"] == True  # noqa: E712
    assert classified.loc[0, "exclusion_reason"] == "reserved_for_calibration"


def test_holdout_overlap_fails_closed() -> None:
    with pytest.raises(ClosureContractError, match="Holdout overlap"):
        build_eligibility.classify_sequence_frame(
            pd.DataFrame([_sequence_row()]),
            model_id="P0",
            base_seed=1729,
            holdout_keys={("wqp", "wqp:test")},
        )


def test_v1_internal_holdout_token_is_recognized(tmp_path) -> None:
    assignment = tmp_path / "data/closure_v1/closure_holdout_assignment.csv"
    assignment.parent.mkdir(parents=True)
    assignment.write_text(
        "source_id,site_id,assignment_role\n"
        "wqp,wqp:development,development\n"
        "wqp,wqp:held,internal_holdout\n",
        encoding="utf-8",
    )
    assert build_eligibility._holdout_keys(tmp_path) == {("wqp", "wqp:held")}


def _known_denominator_ledger() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for role, intent, eligible, locations in (
        ("training", 8352, 7909, 250),
        ("model_selection", 1061, 1016, 60),
        ("calibration_threshold", 319, 302, 40),
    ):
        for index in range(intent):
            is_eligible = index < eligible
            rows.append(
                {
                    "model_id": "P0",
                    "base_seed": 1729,
                    "time_role": role,
                    "source_id": "wqp",
                    "site_id": f"wqp:{role}:{index % locations}",
                    "intent_to_fit": role != "calibration_threshold",
                    "shared_fit_eligible": role != "calibration_threshold" and is_eligible,
                    "shared_calibration_eligible": role == "calibration_threshold" and is_eligible,
                }
            )
    return pd.DataFrame(rows)


def test_known_8925_of_9413_authorizes_fit() -> None:
    summary = build_eligibility.authorization_summary(
        _known_denominator_ledger(), validate_eligibility_policy()
    )
    assert summary["authorized"] is True
    assert summary["slots"][0]["shared_fit_eligible_rows"] == 8925
    assert summary["slots"][0]["fit_intent_rows"] == 9413


def test_fraction_below_point_90_fails_closed() -> None:
    ledger = _known_denominator_ledger()
    fit_indexes = ledger.index[ledger["shared_fit_eligible"]]
    ledger.loc[fit_indexes[8000:], "shared_fit_eligible"] = False
    summary = build_eligibility.authorization_summary(ledger, validate_eligibility_policy())
    assert summary["authorized"] is False


def test_post_2021_row_fails_before_ledger_output() -> None:
    row = copy.deepcopy(_sequence_row(role="calibration_threshold"))
    row["origin_year_month"] = "2022-01"
    row["target_year_month"] = "2022-02"
    with pytest.raises(ClosureContractError, match="Post-2021"):
        build_eligibility.classify_sequence_frame(
            pd.DataFrame([row]), model_id="P0", base_seed=1729, holdout_keys=set()
        )
