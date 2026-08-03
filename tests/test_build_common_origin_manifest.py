from __future__ import annotations

from collections.abc import Iterable

import pandas as pd
import pytest

from src.experiments.build_closure_holdout import PRECURSOR_READ_COLUMNS
from src.experiments.build_common_origin_manifest import (
    FULL_KEY_COLUMNS,
    HORIZONS_MONTHS,
    MODEL_IDS,
    ORIGIN_KEY_COLUMNS,
    TARGET_KEY_COLUMNS,
    add_model_contract_statuses,
    attach_target_availability,
    build_intent_origin_rows,
    validate_common_origin_rows,
)
from src.experiments.closure_development_guard import (
    DevelopmentGate,
    DevelopmentGuardError,
    load_development_gate,
)


EXPECTED_MODEL_STATUSES = {
    "B0": "eligible",
    "B1": "eligible_after_strict_lineage_test",
    "B2": "eligible_after_feature_allowlist_test",
    "F0": "eligible_after_strict_lineage_test",
    "F1": "eligible_after_holdout_excluding_refit",
    "P0": "eligible_after_holdout_excluding_refit",
    "P1": "eligible_after_holdout_excluding_refit",
    "M0": "blocked_pending_strict_adapter",
}


@pytest.fixture(scope="module")
def real_gate() -> DevelopmentGate:
    return load_development_gate(validate_repository=False)


def _real_key(gate: DevelopmentGate, *, holdout: bool = False) -> tuple[str, str]:
    keys = gate.holdout_keys if holdout else gate.development_keys
    return sorted(keys)[0]


def _precursor_panel(
    key: tuple[str, str],
    *,
    start: str,
    end: str,
    missing_months: Iterable[str] = (),
) -> pd.DataFrame:
    months = pd.period_range(start, end, freq="M").astype(str)
    missing = set(missing_months)
    months = [month for month in months if month not in missing]
    source_id, site_id = key
    rows = len(months)
    frame = pd.DataFrame(
        {
            "source_id": [source_id] * rows,
            "site_id": [site_id] * rows,
            "year_month": months,
            "mean_TP_ugL": [20.0] * rows,
            "mean_TN_ugL": [400.0] * rows,
            "mean_temperature_C": [18.0] * rows,
            "mean_secchi_depth_m": [1.5] * rows,
            "mean_turbidity_NTU": [3.0] * rows,
            "mean_DO_mgL": [8.0] * rows,
            "mean_pH": [7.5] * rows,
        }
    )
    assert frame.columns.tolist() == PRECURSOR_READ_COLUMNS
    return frame


def _origin_months(frame: pd.DataFrame) -> set[str]:
    return set(frame["origin_year_month"].astype(str))


def _one_selection_origin(
    gate: DevelopmentGate,
    key: tuple[str, str],
) -> pd.DataFrame:
    panel = _precursor_panel(key, start="2018-02", end="2019-01")
    intent, _ = build_intent_origin_rows(panel, gate)
    assert set(intent["origin_year_month"]) == {"2019-01"}
    return intent


def test_twelve_month_gap_excludes_affected_origin(real_gate: DevelopmentGate) -> None:
    key = _real_key(real_gate)
    panel = _precursor_panel(
        key,
        start="2017-01",
        end="2018-09",
        missing_months={"2018-03"},
    )

    intent, audit = build_intent_origin_rows(panel, real_gate)

    assert "2018-02" in _origin_months(intent)
    assert "2018-09" not in _origin_months(intent)
    assert audit.monthly_status_rows == len(panel)
    assert audit.input_eligible_month_rows == len(panel)


def test_history_may_cross_into_model_selection_role(real_gate: DevelopmentGate) -> None:
    key = _real_key(real_gate)

    intent = _one_selection_origin(real_gate, key)

    assert len(intent) == 3
    assert set(intent["time_role"]) == {"model_selection"}
    assert set(intent["history_start_year_month"]) == {"2018-02"}
    assert set(intent["history_end_year_month"]) == {"2019-01"}


def test_september_origins_are_retained_and_october_origins_are_excluded(
    real_gate: DevelopmentGate,
) -> None:
    key = _real_key(real_gate)
    panel = _precursor_panel(key, start="2017-10", end="2021-12")

    intent, audit = build_intent_origin_rows(panel, real_gate)
    origins = _origin_months(intent)

    assert {"2018-09", "2020-09", "2021-09"}.issubset(origins)
    assert {"2018-10", "2020-10", "2021-10"}.isdisjoint(origins)
    roles = (
        intent.loc[
            intent["origin_year_month"].isin(["2018-09", "2020-09", "2021-09"]),
            ["origin_year_month", "time_role"],
        ]
        .drop_duplicates()
        .set_index("origin_year_month")["time_role"]
        .to_dict()
    )
    assert roles == {
        "2018-09": "training",
        "2020-09": "model_selection",
        "2021-09": "calibration_threshold",
    }
    assert audit.excluded_role_crossing_origins == 6
    assert audit.excluded_locked_evaluation_origins == 3


def test_every_retained_origin_has_exactly_three_horizon_rows(
    real_gate: DevelopmentGate,
) -> None:
    key = _real_key(real_gate)
    panel = _precursor_panel(key, start="2017-10", end="2021-12")

    intent, _ = build_intent_origin_rows(panel, real_gate)
    grouped = intent.groupby(ORIGIN_KEY_COLUMNS, sort=False)

    assert grouped.size().eq(3).all()
    assert grouped["horizon_months"].agg(lambda values: set(values.astype(int))).eq(
        set(HORIZONS_MONTHS)
    ).all()
    assert intent["complete_horizon_geometry"].astype(bool).all()


def test_availability_is_left_joined_and_missing_h2_keeps_the_origin(
    real_gate: DevelopmentGate,
) -> None:
    key = _real_key(real_gate)
    intent = _one_selection_origin(real_gate, key)
    target_keys = intent.loc[intent["horizon_months"].isin([1, 3]), TARGET_KEY_COLUMNS].copy()

    attached = attach_target_availability(intent, target_keys, real_gate)

    pd.testing.assert_frame_equal(
        attached[FULL_KEY_COLUMNS].reset_index(drop=True),
        intent[FULL_KEY_COLUMNS].reset_index(drop=True),
    )
    assert len(attached) == 3
    availability = attached.set_index("horizon_months")["target_evaluable"].to_dict()
    assert availability == {1: True, 2: False, 3: True}
    assert attached["target_evaluable_h1"].all()
    assert not attached["target_evaluable_h2"].any()
    assert attached["target_evaluable_h3"].all()
    assert not attached["complete_targets_evaluable"].any()


def test_duplicate_target_availability_keys_fail(real_gate: DevelopmentGate) -> None:
    key = _real_key(real_gate)
    intent = _one_selection_origin(real_gate, key)
    target_keys = intent[TARGET_KEY_COLUMNS].copy()
    target_keys = pd.concat([target_keys, target_keys.iloc[[0]]], ignore_index=True)

    with pytest.raises(DevelopmentGuardError, match="duplicate exact keys"):
        attach_target_availability(intent, target_keys, real_gate)


def test_conflicting_target_month_fails_arithmetic(real_gate: DevelopmentGate) -> None:
    key = _real_key(real_gate)
    intent = _one_selection_origin(real_gate, key)
    target_keys = intent[TARGET_KEY_COLUMNS].copy()
    target_keys.loc[target_keys["horizon_months"].eq(1), "target_year_month"] = "2019-03"

    with pytest.raises(DevelopmentGuardError, match=r"origin\+horizon target arithmetic"):
        attach_target_availability(intent, target_keys, real_gate)


def test_ids_and_output_order_are_invariant_to_panel_row_order(
    real_gate: DevelopmentGate,
) -> None:
    key = _real_key(real_gate)
    panel = _precursor_panel(key, start="2017-01", end="2018-09")

    ordered, _ = build_intent_origin_rows(panel, real_gate)
    shuffled, _ = build_intent_origin_rows(
        panel.sample(frac=1.0, random_state=20260803).reset_index(drop=True),
        real_gate,
    )

    pd.testing.assert_frame_equal(ordered, shuffled)
    expected_order = ordered.sort_values(FULL_KEY_COLUMNS, kind="mergesort").reset_index(drop=True)
    pd.testing.assert_frame_equal(ordered, expected_order)
    assert ordered["common_origin_id"].str.fullmatch(r"[0-9a-f]{64}").all()
    assert ordered["evaluation_unit_id"].str.fullmatch(r"[0-9a-f]{64}").all()
    assert not ordered["evaluation_unit_id"].duplicated().any()


def test_real_holdout_key_is_rejected_from_synthetic_panel(
    real_gate: DevelopmentGate,
) -> None:
    holdout_key = _real_key(real_gate, holdout=True)
    panel = _precursor_panel(holdout_key, start="2018-02", end="2019-01")

    with pytest.raises(DevelopmentGuardError, match="internal-holdout"):
        build_intent_origin_rows(panel, real_gate)


def test_validated_manifest_has_no_chla_metadata_and_exact_model_statuses(
    real_gate: DevelopmentGate,
) -> None:
    key = _real_key(real_gate)
    intent = _one_selection_origin(real_gate, key)
    attached = attach_target_availability(intent, intent[TARGET_KEY_COLUMNS], real_gate)

    with_statuses = add_model_contract_statuses(attached)
    validated = validate_common_origin_rows(with_statuses, real_gate)

    assert set(EXPECTED_MODEL_STATUSES) == set(MODEL_IDS)
    for model_id, expected in EXPECTED_MODEL_STATUSES.items():
        assert set(validated[f"model_contract_status_{model_id}"]) == {expected}
    assert not any(
        "chla" in column.lower() or "chlorophyll" in column.lower()
        for column in validated.columns
    )
    assert "split" not in validated.columns
    assert "model_available" not in validated.columns
    assert "failure_code" not in validated.columns

    contaminated = validated.assign(chla_missingness_metadata=False)
    with pytest.raises(DevelopmentGuardError, match="forbidden Chl-a lineage"):
        validate_common_origin_rows(contaminated, real_gate)
