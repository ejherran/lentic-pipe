from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pytest

from src.experiments import run_closure_mifal as runner
from src.mifal import closure_panel_adapter as adapter
from src.mifal.ed_t2 import RawInput


VALID_VALUES = {
    "Tw": 22.0,
    "TP": 45.0,
    "TN": 800.0,
    "Secchi": 1.5,
    "Turb": 10.0,
    "DOb": 7.0,
}


def _panel_row(
    site_id: str,
    *,
    variables: tuple[str, ...],
    year_month: str = "2018-01",
) -> dict[str, Any]:
    row: dict[str, Any] = {column: np.nan for column in adapter.PANEL_PROJECTION_COLUMNS}
    row.update({"source_id": "wqp", "site_id": site_id, "year_month": year_month})
    by_variable = {spec.mifal_variable: spec for spec in adapter.CLOSURE_VARIABLE_SPECS}
    for variable in variables:
        spec = by_variable[variable]
        row[spec.value_column] = VALID_VALUES[variable]
        row[spec.n_obs_column] = 3.0
        row[spec.qc_ok_rate_column] = 1.0
        row[spec.std_column] = 0.5
    return row


def _synthetic_frames(
    *,
    second_variables: tuple[str, ...] = ("Tw",),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    for site_id in ("site-a", "site-b"):
        for horizon in runner.HORIZONS:
            rows.append(
                {
                    "source_id": "wqp",
                    "site_id": site_id,
                    "common_origin_id": f"origin-{site_id}",
                    "evaluation_unit_id": f"origin-{site_id}-h{horizon}",
                    "holdout_group_id": f"wqp::{site_id}",
                    "assignment_role": "development",
                    "time_role": "training",
                    "origin_year_month": "2018-01",
                    "target_year_month": f"2018-0{horizon + 1}",
                    "horizon_months": horizon,
                }
            )
    common = pd.DataFrame(rows, columns=runner.KEY_COLUMNS)
    panel = pd.DataFrame(
        [
            _panel_row("site-a", variables=("Tw", "TP")),
            _panel_row("site-b", variables=second_variables),
        ],
        columns=adapter.PANEL_PROJECTION_COLUMNS,
    )
    return common, panel


def test_strict_projection_is_interleaved_keys_plus_exactly_24_physical_columns() -> None:
    assert adapter.validate_projection() == adapter.PANEL_PROJECTION_COLUMNS
    assert len(adapter.PANEL_PROJECTION_COLUMNS) == 27
    assert len(adapter.PANEL_PHYSICAL_COLUMNS) == 24
    assert adapter.PANEL_PROJECTION_COLUMNS[:7] == (
        "source_id",
        "site_id",
        "year_month",
        "mean_temperature_C",
        "n_obs_temperature_C",
        "qc_ok_rate_temperature_C",
        "std_temperature_C",
    )
    lowered = "\n".join(adapter.PANEL_PROJECTION_COLUMNS).lower()
    assert "chlorophyll" not in lowered
    assert "risk_chla" not in lowered


def test_strict_adapter_has_no_direct_historical_adapter_import() -> None:
    source = Path(adapter.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
    assert "src.mifal.panel_adapter" not in imported


def test_project_closure_panel_drops_every_extra_column() -> None:
    row = _panel_row("site-a", variables=("Tw", "TP"))
    row["mean_chlorophyll_a_ugL"] = 99.0
    projected = adapter.project_closure_panel(pd.DataFrame([row]))
    assert tuple(projected.columns) == adapter.PANEL_PROJECTION_COLUMNS
    assert "mean_chlorophyll_a_ugL" not in projected


def test_payload_maps_tn_units_and_locked_quality() -> None:
    row = _panel_row("site-a", variables=("Tw", "TN"))
    payload = adapter.panel_row_to_closure_mifal_payload(row)
    assert tuple(payload) == ("Tw", "TN")
    assert payload["TN"].value == pytest.approx(0.8)
    assert payload["TN"].source_fit == pytest.approx(0.95)
    assert payload["TN"].source_quality == pytest.approx(0.8)
    assert payload["TN"].age_days == pytest.approx(15.0)


@pytest.mark.parametrize("n_obs", [None, np.nan, 0.0, 0.5])
def test_payload_requires_finite_n_obs_at_least_one(n_obs: float | None) -> None:
    row = _panel_row("site-a", variables=("Tw", "TP"))
    row["n_obs_TP_ugL"] = n_obs
    payload = adapter.panel_row_to_closure_mifal_payload(row)
    assert "TP" not in payload


@pytest.mark.parametrize(("qc", "expected"), [(-3.0, 0.0), (2.0, 0.8), (None, 0.6)])
def test_payload_clips_qc_and_uses_missing_qc_fallback(
    qc: float | None,
    expected: float,
) -> None:
    row = _panel_row("site-a", variables=("Tw",))
    row["qc_ok_rate_temperature_C"] = qc
    payload = adapter.panel_row_to_closure_mifal_payload(row)
    assert payload["Tw"].source_quality == pytest.approx(expected)


def test_payload_eligibility_requires_two_distinct_ecological_groups() -> None:
    same_group = adapter.panel_row_to_closure_mifal_payload(
        _panel_row("site-a", variables=("TP", "TN"))
    )
    two_groups = adapter.panel_row_to_closure_mifal_payload(
        _panel_row("site-a", variables=("Tw", "TP"))
    )
    assert adapter.observed_evidence_groups(same_group) == ("nutrients",)
    assert not adapter.payload_is_eligible(same_group)
    assert adapter.observed_evidence_groups(two_groups) == ("temperature", "nutrients")
    assert adapter.payload_is_eligible(two_groups)


def test_default_v5_config_digest_is_frozen() -> None:
    assert runner.default_config_record() == {
        "bytes": 3217,
        "sha256": "8ad6314fbd833945d9cbd3d84267f0d18a7e79a53fbd61cdea89f703e05f4ded",
    }


def test_model_spec_distinguishes_structural_prior_from_observed_memory() -> None:
    records = [
        {"path": runner.RUNNER_SOURCE_PATH.as_posix(), "bytes": 1, "sha256": "1" * 64},
        {"path": runner.ADAPTER_SOURCE_PATH.as_posix(), "bytes": 2, "sha256": "2" * 64},
        {"path": runner.MIFAL_CORE_PATH.as_posix(), "bytes": 3, "sha256": "3" * 64},
    ]
    spec = runner.model_spec_payload(records)
    assert spec["core_version"] == "5.0.0"
    assert spec["observed_memory_inputs"] == []
    assert spec["call_policy"] == {
        "assimilate": False,
        "update_state": False,
        "compute_voi": False,
        "state_carry_between_rows": False,
    }
    assert spec["structural_global_priors"] == {
        "initial_state": [0.05, 0.35],
        "gammaM": 0.28,
        "memory_fallback": [0.0, 0.35],
        "interpretation": "global_constant_prior_not_observed_chlorophyll_memory",
    }
    assert len(spec["source_code"]) == 3
    assert spec["threadpool_limit"] == 1
    assert spec["legacy_adapter_direct_import_authorized"] is False
    assert spec["legacy_adapter_invocation_authorized"] is False
    assert spec["legacy_adapter_data_projection_authorized"] is False
    assert (
        spec["package_initializer_symbol_loading"]
        == "incidental_non_authoritative_no_io"
    )


def test_raw_contract_is_exactly_28_columns_in_runtime_order() -> None:
    assert len(runner.RAW_PREDICTION_COLUMNS) == 28
    assert runner.RAW_PREDICTION_COLUMNS[-3:] == (
        "evidence_group_count",
        "payload_variable_count",
        "payload_variables",
    )
    assert runner.raw_prediction_contract()["columns"] == runner.load_runtime_contract()[
        "outputs"
    ]["raw_prediction_contract"]["columns"]


def test_build_m0_retains_ineligible_rows_with_null_numeric_outputs() -> None:
    common, panel = _synthetic_frames()
    raw, availability = runner.build_m0_predictions(common, panel)
    assert len(raw) == 6
    assert len(availability) == 2
    assert raw["availability_status"].value_counts().to_dict() == {
        "success": 3,
        "input_ineligible": 3,
    }
    ineligible = raw[raw["availability_status"] == "input_ineligible"]
    assert ineligible["failure_reason"].eq("strict_non_chla_evidence_incomplete").all()
    assert ineligible[
        ["raw_score", "predicted_bloom_probability", "interval_lower", "interval_upper", "data_reliability"]
    ].isna().all().all()
    assert ineligible["evidence_group_count"].eq(1).all()


def test_build_m0_success_is_raw_uncalibrated_and_never_carries_state() -> None:
    common, panel = _synthetic_frames(second_variables=("Secchi", "DOb"))
    raw, availability = runner.build_m0_predictions(common, panel)
    assert availability["availability_status"].eq("success").all()
    assert raw["predicted_bloom_probability"].isna().all()
    assert raw["score_semantics"].eq(
        "mifal_type2_conservative_raw_risk_uncalibrated"
    ).all()
    assert raw["candidate"].eq("mifal_ed_t2_v5_defaults").all()
    assert not raw["selected_family"].any()
    assert raw["model_seed"].isna().all()
    assert raw["upstream_state_seed"].isna().all()
    assert raw["raw_score"].between(0.0, 1.0).all()


def test_build_m0_calls_core_with_all_closed_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    original = runner.MIFALEDT2.step
    calls: list[dict[str, Any]] = []

    def spy_step(
        self: runner.MIFALEDT2,
        data: Mapping[str, RawInput],
        dt_days: float = 7.0,
        assimilate: bool = True,
        update_state: bool = False,
        state_update_target: str = "forecast",
        compute_voi: bool = True,
    ) -> dict[str, object]:
        calls.append(
            {
                "dt_days": dt_days,
                "assimilate": assimilate,
                "update_state": update_state,
                "state_update_target": state_update_target,
                "compute_voi": compute_voi,
            }
        )
        return original(
            self,
            data,
            dt_days=dt_days,
            assimilate=assimilate,
            update_state=update_state,
            state_update_target=state_update_target,
            compute_voi=compute_voi,
        )

    monkeypatch.setattr(runner.MIFALEDT2, "step", spy_step)
    common, panel = _synthetic_frames(second_variables=("Secchi", "DOb"))
    runner.build_m0_predictions(common, panel)
    assert len(calls) == 6
    assert all(call["assimilate"] is False for call in calls)
    assert all(call["update_state"] is False for call in calls)
    assert all(call["compute_voi"] is False for call in calls)
    assert {call["dt_days"] for call in calls} == {
        30.4375,
        60.875,
        91.3125,
    }


def test_core_exception_aborts_instead_of_becoming_a_row_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: Any, **kwargs: Any) -> dict[str, object]:
        raise ArithmeticError("synthetic core failure")

    monkeypatch.setattr(runner.MIFALEDT2, "step", fail)
    common, panel = _synthetic_frames(second_variables=("Secchi", "DOb"))
    with pytest.raises(ArithmeticError, match="synthetic core failure"):
        runner.build_m0_predictions(common, panel)


def test_nonfinite_core_result_aborts_the_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    original = runner.MIFALEDT2.step

    def nonfinite(self: Any, *args: Any, **kwargs: Any) -> dict[str, object]:
        result = original(self, *args, **kwargs)
        result["risk_conservative"] = float("nan")
        return result

    monkeypatch.setattr(runner.MIFALEDT2, "step", nonfinite)
    common, panel = _synthetic_frames(second_variables=("Secchi", "DOb"))
    with pytest.raises(runner.ClosureMIFALRunError, match="raw_score"):
        runner.build_m0_predictions(common, panel)


def test_raw_payload_encoding_must_match_counts_and_groups() -> None:
    common, panel = _synthetic_frames(second_variables=("Secchi", "DOb"))
    raw, _ = runner.build_m0_predictions(common, panel)
    wrong_count = raw.copy()
    wrong_count.loc[0, "payload_variable_count"] = 6
    with pytest.raises(runner.ClosureMIFALRunError, match="ordered payload subsequence"):
        runner.canonical_m0_raw_frame(wrong_count)
    wrong_groups = raw.copy()
    wrong_groups.loc[0, "evidence_group_count"] = 4
    with pytest.raises(runner.ClosureMIFALRunError, match="disagrees"):
        runner.canonical_m0_raw_frame(wrong_groups)


def test_raw_arrow_schema_is_exact_and_probability_is_nullable_null() -> None:
    common, panel = _synthetic_frames(second_variables=("Secchi", "DOb"))
    raw, _ = runner.build_m0_predictions(common, panel)
    table = runner.raw_arrow_table(raw)
    assert table.schema == runner.RAW_ARROW_SCHEMA
    assert table.num_columns == 28
    assert table.schema.field("evidence_group_count").type == pa.int8()
    assert table.column("predicted_bloom_probability").null_count == len(raw)


def test_availability_summary_has_exact_20_rows_and_all_dimensions() -> None:
    common, panel = _synthetic_frames()
    raw, availability = runner.build_m0_predictions(common, panel)
    summary = runner.availability_summary(raw, availability)
    assert len(summary) == 20
    assert set(summary["dimension"]) == {
        "overall",
        "availability_status",
        "evidence_group_count",
        "time_role",
        "horizon_months",
        "payload_variable",
    }
    success = summary[
        (summary["dimension"] == "availability_status") & (summary["value"] == "success")
    ].iloc[0]
    assert (success["intent_origins"], success["raw_rows"]) == (1, 3)


def test_snapshot_validator_can_be_exercised_on_synthetic_denominators(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    common, panel = _synthetic_frames(second_variables=("Secchi", "DOb"))
    raw, availability = runner.build_m0_predictions(common, panel)
    monkeypatch.setattr(runner, "EXPECTED_INTENT_ORIGINS", 2)
    monkeypatch.setattr(runner, "EXPECTED_COMMON_ROWS", 6)
    monkeypatch.setattr(runner, "EXPECTED_GROUP_COUNT_ORIGINS", {2: 2})
    monkeypatch.setattr(runner, "EXPECTED_GROUP_COUNT_ROWS", {2: 6})
    monkeypatch.setattr(
        runner,
        "EXPECTED_VARIABLE_COVERAGE",
        {"Tw": 1, "TP": 1, "TN": 0, "Secchi": 1, "Turb": 0, "DOb": 1},
    )
    monkeypatch.setattr(runner, "EXPECTED_ORIGINS_BY_ROLE", {"training": 2})
    result = runner.validate_snapshot_availability(raw, availability)
    assert result["eligible_origins"] == 2
    assert result["rows_by_horizon"] == {1: 2, 2: 2, 3: 2}


def test_manifest_serializer_requires_completion_marker_last() -> None:
    assert runner._manifest_json_bytes(
        {"status": "ok", "completion_marker_written_last": True}
    ).endswith(b"\n")
    with pytest.raises(runner.ClosureMIFALRunError, match="last top-level key"):
        runner._manifest_json_bytes(
            {"completion_marker_written_last": True, "status": "wrong-order"}
        )


def test_output_transaction_rolls_back_every_owned_inode_on_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    first = Path("bundle/first.json")
    second = Path("bundle/second.json")
    with pytest.raises(RuntimeError, match="guard release failed"):
        with runner.OutputTransaction() as transaction:
            transaction.publish_bytes(b"one", first)
            transaction.publish_bytes(b"two", second)
            raise RuntimeError("guard release failed")
    assert not (tmp_path / first).exists()
    assert not (tmp_path / second).exists()
    assert not (tmp_path / f"{first}.tmp").exists()
    assert not (tmp_path / f"{second}.tmp").exists()


def test_output_transaction_refuses_to_clobber_existing_final(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    path = Path("bundle/final.json")
    with runner.OutputTransaction() as transaction:
        transaction.publish_bytes(b"first", path)
    with pytest.raises(runner.ClosureMIFALRunError, match="overwrite final"):
        with runner.OutputTransaction() as transaction:
            transaction.publish_bytes(b"second", path)
    assert (tmp_path / path).read_bytes() == b"first"


def test_output_transaction_rejects_symlinked_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    (tmp_path / "real").mkdir()
    (tmp_path / "linked").symlink_to(tmp_path / "real", target_is_directory=True)
    with pytest.raises(runner.ClosureMIFALRunError, match="not a real directory"):
        with runner.OutputTransaction() as transaction:
            transaction.publish_bytes(b"blocked", Path("linked/output.json"))
    assert not (tmp_path / "real/output.json").exists()


def test_guard_is_exclusive_and_released_by_owned_inode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(runner, "GUARD_PATH", Path("tmp/mifal.guard"))
    guard = runner._acquire_guard()
    with pytest.raises(runner.ClosureMIFALRunError, match="already reserved"):
        runner._acquire_guard()
    runner._release_guard(guard)
    assert not (tmp_path / "tmp/mifal.guard").exists()


def test_guard_release_occurs_inside_output_transaction_scope() -> None:
    source = Path(runner.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    output_scopes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.With)
        and any(
            isinstance(item.context_expr, ast.Call)
            and isinstance(item.context_expr.func, ast.Name)
            and item.context_expr.func.id == "OutputTransaction"
            for item in node.items
        )
    ]
    assert len(output_scopes) == 1
    calls = [
        node.func.id
        for node in ast.walk(output_scopes[0])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert "_release_guard" in calls
    assert "_assert_exact_published_namespace" in calls


def test_main_requires_effective_authority_before_preflight(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    events: list[str] = []
    authority = {"sentinel": True}

    def gate() -> dict[str, Any]:
        events.append("authority")
        return authority

    def preflight(value: dict[str, Any]) -> dict[str, Any]:
        assert value is authority
        events.append("preflight")
        return {"status": "ready"}

    monkeypatch.setattr(runner, "_require_effective_authority", gate)
    monkeypatch.setattr(runner, "_preflight_with_verified_authority", preflight)
    assert runner.main(["--check-only"]) == 0
    assert events == ["authority", "preflight"]
    assert '"status": "ready"' in capsys.readouterr().out


def test_runner_has_no_target_artifact_path_or_legacy_adapter_import() -> None:
    source = Path(runner.__file__).read_text(encoding="utf-8")
    assert "data/targets" not in source
    assert "src.mifal.panel_adapter" not in source
    assert "threadpool_limits(limits=1)" in source
