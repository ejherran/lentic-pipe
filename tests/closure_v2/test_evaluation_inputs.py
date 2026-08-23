from __future__ import annotations

from pathlib import Path

import pytest

from src.experiments.closure_v2 import build_evaluation_inputs as inputs


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "mean_TP_ugL": None,
        "mean_TN_ugL": None,
        "TN_TP_ratio": None,
        "mean_DO_mgL": None,
        "mean_pH": None,
        "mean_turbidity_NTU": None,
        "mean_secchi_depth_m": None,
        "mean_temperature_C": None,
    }
    row.update(overrides)
    return row


def test_input_month_requires_each_allowed_module() -> None:
    assert inputs.input_month_eligible(
        _row(mean_TP_ugL=25.0, mean_DO_mgL=8.0, mean_temperature_C=18.0)
    )
    assert not inputs.input_month_eligible(
        _row(mean_TP_ugL=25.0, mean_DO_mgL=8.0)
    )
    assert not inputs.input_month_eligible(
        _row(mean_TP_ugL=25.0, mean_temperature_C=18.0)
    )
    assert not inputs.input_month_eligible(
        _row(mean_DO_mgL=8.0, mean_temperature_C=18.0)
    )


def test_input_month_rejects_nonfinite_support() -> None:
    assert not inputs.input_month_eligible(
        _row(mean_TP_ugL=float("nan"), mean_DO_mgL=8.0, mean_temperature_C=18.0)
    )


def test_candidate_digest_uses_sealed_nul_framing() -> None:
    keys = [("wqp", "site-a", "2022-01"), ("wqp", "site-b", "2022-02")]
    assert inputs._candidate_digest(keys) == "7993090a542e61aa90c8d85aed4f00b84279b7f2507bea752ccb7d48448e547a"


def test_parquet_contract_forbids_outcome_semantics() -> None:
    with pytest.raises(inputs.EvaluationInputError, match="Forbidden"):
        inputs._validate_columns(["source_id", "target_value"])


def test_preflight_is_nonwriting_when_reconstruction_is_stubbed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        inputs,
        "_reconstruct",
        lambda root: (
            {
                "inventory": [object()] * inputs.EXPECTED_LOCATIONS,
                "candidate_keys": [object()] * inputs.EXPECTED_ORIGINS,
                "candidate_digest": inputs.EXPECTED_KEY_DIGEST,
            },
            {},
            {"status": "model_lock_effective"},
            {},
        ),
    )
    result = inputs.preflight(tmp_path)
    assert result["status"] == "ready_to_materialize"
    assert result["candidate_location_count"] == 137
    assert result["intent_origins_per_horizon"] == 2_286
    assert list(tmp_path.rglob("*")) == []
