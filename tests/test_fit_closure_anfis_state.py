from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from src.experiments import fit_closure_anfis_state as anfis_adapter
from src.experiments.closure_contract import load_yaml_mapping
from src.experiments.closure_development_guard import (
    DevelopmentGate,
    DevelopmentScanAudit,
    TimeRoleBounds,
)
from src.experiments.closure_runtime_contract import (
    DEFAULT_RUNTIME_CONFIG,
    ClosureRuntimeContractError,
)


def _runtime() -> dict[str, Any]:
    return load_yaml_mapping(DEFAULT_RUNTIME_CONFIG)


def _gate(development_sites: tuple[str, ...]) -> DevelopmentGate:
    assignment = pd.DataFrame(
        [
            {
                "source_id": "wqp",
                "site_id": site_id,
                "holdout_group_id": f"wqp::{site_id}",
                "assignment_role": "development",
            }
            for site_id in development_sites
        ]
        + [
            {
                "source_id": "wqp",
                "site_id": "H",
                "holdout_group_id": "wqp::H",
                "assignment_role": "internal_holdout",
            }
        ]
    )
    return DevelopmentGate(
        assignment_path=Path("assignment.csv"),
        assignment_sha256="a" * 64,
        holdout_manifest_path=Path("holdout.json"),
        holdout_manifest_sha256="b" * 64,
        protocol_lock_path=Path("protocol.json"),
        protocol_lock_sha256="c" * 64,
        locked_repository_head="d" * 40,
        repository_validated=False,
        bounds=TimeRoleBounds(
            training_end="2018-12",
            model_selection_start="2019-01",
            model_selection_end="2020-12",
            calibration_threshold_start="2021-01",
            calibration_threshold_end="2021-12",
            locked_evaluation_start="2022-01",
        ),
        _assignment=assignment,
    )


def _roles(site_id: str, month: str = "2018-01") -> dict[str, Any]:
    return {
        "source_id": "wqp",
        "site_id": site_id,
        "year_month": month,
        "assignment_role": "development",
        "time_role": "training",
    }


def _join_audits(
    audit: anfis_adapter.PanelAnchorJoinAudit,
) -> dict[str, anfis_adapter.PanelAnchorJoinAudit]:
    return {"training_candidates": audit, "full_development": audit}


def _panel_row(site_id: str, *, tp: float = 100.0) -> dict[str, Any]:
    return {
        **_roles(site_id),
        "mean_TP_ugL": tp,
        "mean_TN_ugL": 300.0,
        "TN_TP_ratio": 12.0,
        "mean_DO_mgL": 7.0,
        "mean_pH": 8.0,
        "mean_turbidity_NTU": 27.5,
        "mean_secchi_depth_m": 1.75,
        "mean_temperature_C": 30.0,
    }


def _anchor_row(site_id: str) -> dict[str, Any]:
    return {**_roles(site_id), "yN": 0.8, "yF": 0.7, "yT_no_chla": 0.6}


def test_panel_anchor_join_is_one_to_one_conservative_and_feature_exact() -> None:
    panel = pd.DataFrame([_panel_row("A"), _panel_row("B")])
    anchor = pd.DataFrame([_anchor_row("A"), _anchor_row("C")])

    joined, audit = anfis_adapter.join_anfis_sources(
        panel,
        anchor,
        runtime=_runtime(),
        gate=_gate(("A", "B", "C")),
    )

    assert joined["site_id"].tolist() == ["A"]
    assert audit.filtered_panel_rows == 2
    assert audit.filtered_anchor_rows == 2
    assert audit.matched_rows == 1
    assert audit.unmatched_panel_rows == 1
    assert audit.unmatched_anchor_rows == 1
    assert joined.loc[0, "tp_pressure"] == pytest.approx(1.0)
    assert joined.loc[0, "tn_pressure"] == pytest.approx(0.0)
    assert joined.loc[0, "ratio_imbalance_pressure"] == pytest.approx(0.5)
    assert joined.loc[0, "temp_favorable"] == pytest.approx(1.0)


def test_panel_anchor_join_rejects_duplicates_and_role_disagreement() -> None:
    panel = pd.DataFrame([_panel_row("A"), _panel_row("A")])
    anchor = pd.DataFrame([_anchor_row("A")])
    with pytest.raises(ClosureRuntimeContractError, match="duplicate"):
        anfis_adapter.join_anfis_sources(
            panel,
            anchor,
            runtime=_runtime(),
            gate=_gate(("A",)),
        )


def test_surface_loader_filters_training_before_candidate_join(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _runtime()
    gate = _gate(("A",))
    panel = pd.DataFrame(
        [
            _panel_row("A"),
            {
                **_panel_row("A"),
                "year_month": "2021-01",
                "time_role": "calibration_threshold",
            },
        ]
    )
    anchor = pd.DataFrame(
        [
            _anchor_row("A"),
            {
                **_anchor_row("A"),
                "year_month": "2021-01",
                "time_role": "calibration_threshold",
            },
        ]
    )
    audit = DevelopmentScanAudit(
        2,
        2,
        0,
        (("training", 1), ("calibration_threshold", 1)),
    )

    def scan(path: Path, *args: Any, columns: tuple[str, ...], **kwargs: Any) -> tuple[pd.DataFrame, DevelopmentScanAudit]:
        del path, args, kwargs
        source = panel if "mean_TP_ugL" in columns else anchor
        return source.loc[:, [*columns, "assignment_role", "time_role"]], audit

    monkeypatch.setattr(anfis_adapter, "scan_development_rows", scan)

    views = anfis_adapter.load_joined_anfis_surface(runtime=runtime, gate=gate)

    assert len(views.full_development) == 2
    assert len(views.training_candidates) == 1
    assert views.training_candidates["year_month"].tolist() == ["2018-01"]
    assert views.full_development_join.matched_rows == 2
    assert views.training_candidate_join.matched_rows == 1
    assert (
        views.full_development_join.matched_keys_sha256
        != views.training_candidate_join.matched_keys_sha256
    )

    panel = pd.DataFrame([_panel_row("A")]).assign(time_role="model_selection")
    with pytest.raises(ClosureRuntimeContractError, match="disagree on time_role"):
        anfis_adapter.join_anfis_sources(
            panel,
            anchor,
            runtime=_runtime(),
            gate=_gate(("A",)),
        )


def test_adapter_preserves_hash_rank_order_for_exact_4096_sample() -> None:
    site_ids = tuple(f"S{index:04d}" for index in range(4096))
    surface = pd.DataFrame(
        [
            {
                **_roles(site_id),
                "yN": 0.5,
                "tp_pressure": 0.2,
                "tn_pressure": 0.3,
                "ratio_imbalance_pressure": 0.4,
            }
            for site_id in site_ids
        ]
    )
    gate = _gate(site_ids)

    selected, keys, audit = anfis_adapter.select_module_training_rows(
        surface,
        runtime=_runtime(),
        gate=gate,
        module="ANFIS-N",
        module_seed=1830,
    )
    reversed_selected, reversed_keys, reversed_audit = anfis_adapter.select_module_training_rows(
        surface.iloc[::-1].reset_index(drop=True),
        runtime=_runtime(),
        gate=gate,
        module="ANFIS-N",
        module_seed=1830,
    )

    assert audit["selected_rows"] == 4096
    assert audit == reversed_audit
    assert keys.to_dict(orient="records") == reversed_keys.to_dict(orient="records")
    assert selected["site_id"].tolist() == keys["site_id"].tolist()
    assert reversed_selected["site_id"].tolist() == reversed_keys["site_id"].tolist()


def _small_all_module_surface(site_ids: tuple[str, ...] = ("A", "B")) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                **_roles(site_id),
                "yN": 0.5,
                "yF": 0.6,
                "yT_no_chla": 0.7,
                "tp_pressure": 0.2,
                "tn_pressure": 0.3,
                "ratio_imbalance_pressure": 0.4,
                "do_good": 0.8,
                "ph_good": 0.7,
                "turbidity_good": 0.6,
                "secchi_good": 0.5,
                "temp_favorable": 0.9,
            }
            for site_id in site_ids
        ]
    )


def test_insufficient_sampler_becomes_machine_readable_unavailable_without_replacement() -> None:
    with pytest.raises(anfis_adapter.AnfisModuleUnavailableError) as raised:
        anfis_adapter.select_module_training_rows(
            _small_all_module_surface(),
            runtime=_runtime(),
            gate=_gate(("A", "B")),
            module="ANFIS-N",
            module_seed=1830,
        )

    evidence = raised.value.evidence
    assert evidence.module == "ANFIS-N"
    assert evidence.base_seed == 1729
    assert evidence.eligible_rows == 2
    assert evidence.required_rows == 4096
    assert evidence.failure_reason == "insufficient_eligible_training_rows"
    assert evidence.replacement_used is False
    assert evidence.audit["selected_rows"] == 0
    assert evidence.audit["selected_keys_sha256"] == anfis_adapter.hashlib.sha256(b"").hexdigest()


def test_slot_sampling_preflights_all_modules_before_any_fit() -> None:
    prepared, unavailable = anfis_adapter.prepare_slot_module_samples(
        _small_all_module_surface(),
        runtime=_runtime(),
        gate=_gate(("A", "B")),
        substreams=anfis_adapter.anfis_module_substreams(1729),
    )

    assert prepared == {}
    assert tuple(unavailable) == anfis_adapter.PRIMARY_MODULES
    assert all(item.replacement_used is False for item in unavailable.values())


def test_only_primary_no_current_modules_are_registered() -> None:
    artifact_tokens = anfis_adapter.ANFIS_MODULE_ARTIFACT_TOKENS
    assert artifact_tokens == {
        "ANFIS-N": "anfis_n",
        "ANFIS-F": "anfis_f",
        "ANFIS-T-no-current": "anfis_t_no_current",
    }
    assert tuple(artifact_tokens) == anfis_adapter.PRIMARY_MODULES
    for module in anfis_adapter.PRIMARY_MODULES:
        features, target = anfis_adapter._module_contract(_runtime(), module)
        assert features
        assert target in {"yN", "yF", "yT_no_chla"}

    with pytest.raises(ClosureRuntimeContractError, match="Unregistered primary"):
        anfis_adapter._module_contract(_runtime(), "ANFIS-T")

    paths = anfis_adapter._slot_paths(_runtime(), 20260612)
    model_paths = {
        module: path.relative_to(anfis_adapter.PROJECT_ROOT).as_posix()
        for module, path in paths["models"].items()
    }
    sample_paths = {
        module: path.relative_to(anfis_adapter.PROJECT_ROOT).as_posix()
        for module, path in paths["samples"].items()
    }
    assert model_paths == {
        "ANFIS-N": "models/closure_v1/anfis/seed_20260612/anfis_n.pt",
        "ANFIS-F": "models/closure_v1/anfis/seed_20260612/anfis_f.pt",
        "ANFIS-T-no-current": (
            "models/closure_v1/anfis/seed_20260612/anfis_t_no_current.pt"
        ),
    }
    assert sample_paths == {
        "ANFIS-N": (
            "reports/closure_v1/01_surface/anfis/seed_20260612/anfis_n_sample_keys.csv"
        ),
        "ANFIS-F": (
            "reports/closure_v1/01_surface/anfis/seed_20260612/anfis_f_sample_keys.csv"
        ),
        "ANFIS-T-no-current": (
            "reports/closure_v1/01_surface/anfis/seed_20260612/"
            "anfis_t_no_current_sample_keys.csv"
        ),
    }
    rendered_module_paths = (*model_paths.values(), *sample_paths.values())
    assert not any("ANFIS-" in path for path in rendered_module_paths)


def test_prediction_uncertainty_uses_raw_module_firing_and_missingness() -> None:
    torch = anfis_adapter._require_torch()

    class FakeModel:
        def eval(self) -> None:
            return None

        def __call__(self, x: Any, return_details: bool = False) -> dict[str, Any]:
            assert return_details is True
            rows = int(x.shape[0])
            return {
                "prediction": torch.full((rows,), 0.4, dtype=torch.float32),
                "firing_strengths": torch.full((rows, 3), 0.25, dtype=torch.float32),
            }

    frame = pd.DataFrame({"temp_favorable": [0.5, np.nan]})
    prediction, sigma = anfis_adapter.predict_primary_module(
        FakeModel(),
        frame,
        runtime=_runtime(),
        module="ANFIS-T-no-current",
    )

    assert prediction.tolist() == pytest.approx([0.4, 0.4])
    assert sigma.tolist() == pytest.approx([0.55, 0.90])


def _dummy_result(
    module: str,
    prediction: list[float],
    uncertainty: list[float],
) -> anfis_adapter.ModuleFitResult:
    return anfis_adapter.ModuleFitResult(
        module=module,
        module_seed=1,
        model=None,
        sample_keys=pd.DataFrame(),
        sample_audit={"base_seed": 1729},
        predictions=np.asarray(prediction, dtype="float64"),
        uncertainty=np.asarray(uncertainty, dtype="float64"),
        metrics={"module": module, "status": "passed"},
        curve=pd.DataFrame(),
        memberships_initial=pd.DataFrame(),
        memberships_final=pd.DataFrame(),
    )


def test_adaptive_state_uses_exact_month_deltas_and_output_allowlist() -> None:
    surface = pd.DataFrame(
        [
            {**_roles("A", "2020-01"), "time_role": "model_selection"},
            {**_roles("A", "2020-02"), "time_role": "model_selection"},
            {**_roles("A", "2020-04"), "time_role": "model_selection"},
        ]
    )
    results = {
        "ANFIS-N": _dummy_result("ANFIS-N", [0.2, 0.5, 0.7], [0.1, 0.1, 0.1]),
        "ANFIS-F": _dummy_result("ANFIS-F", [0.8, 0.4, 0.3], [0.2, 0.2, 0.2]),
        "ANFIS-T-no-current": _dummy_result(
            "ANFIS-T-no-current", [0.3, 0.9, 0.6], [0.3, 0.3, 0.3]
        ),
    }

    observed = anfis_adapter.build_adaptive_state(
        surface,
        results,
        runtime=_runtime(),
        gate=_gate(("A",)),
    )

    expected = _runtime()["primary_autoregressive_state"]["state_export"]["p1_output_columns"]
    assert list(observed.columns) == expected
    by_month = observed.set_index("year_month")
    assert by_month.loc["2020-02", "delta_yN_adaptive"] == pytest.approx(0.3)
    assert by_month.loc["2020-02", "delta_yF_adaptive"] == pytest.approx(-0.4)
    assert by_month.loc["2020-02", "delta_yT_no_chla_adaptive"] == pytest.approx(0.6)
    assert by_month.loc["2020-04", "delta_yN_adaptive"] == 0.0
    assert bool(by_month.loc["2020-04", "delta_previous_month_missing"]) is True
    assert "yT_adaptive" not in observed


def test_seed_is_set_before_model_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    selected = pd.DataFrame(
        [{**_roles("A"), "temp_favorable": 0.5, "yT_no_chla": 0.6}]
    )

    class FakeModel:
        rule_count = 3

        def parameters(self) -> list[Any]:
            return []

        def ordered_centers(self) -> Any:
            return anfis_adapter._require_torch().tensor([[0.1, 0.5, 0.9]])

        def positive_widths(self) -> Any:
            return anfis_adapter._require_torch().tensor([[0.2, 0.2, 0.2]])

        def centers_are_ordered(self) -> bool:
            return True

        def centers_in_unit_interval(self) -> bool:
            return True

    monkeypatch.setattr(
        anfis_adapter,
        "select_module_training_rows",
        lambda *args, **kwargs: (
            selected,
            pd.DataFrame([{"source_id": "wqp", "site_id": "A", "year_month": "2018-01"}]),
            {"base_seed": 1729, "selected_rows": 1},
        ),
    )
    monkeypatch.setattr(
        anfis_adapter,
        "set_closure_anfis_seed",
        lambda seed: events.append(f"seed:{seed}"),
    )
    monkeypatch.setattr(
        anfis_adapter,
        "make_adaptive_anfis",
        lambda **kwargs: (events.append("construct") or FakeModel()),
    )
    monkeypatch.setattr(anfis_adapter, "parameter_snapshot", lambda model: {})
    monkeypatch.setattr(anfis_adapter, "max_parameter_delta", lambda model, before: 1.0)
    monkeypatch.setattr(
        anfis_adapter,
        "train_supervised_anfis",
        lambda *args, **kwargs: [{"epoch": 1.0, "loss": 0.1}],
    )
    monkeypatch.setattr(
        anfis_adapter,
        "_post_update_anchor_metrics",
        lambda *args, **kwargs: (0.05, 0.02),
    )
    monkeypatch.setattr(
        anfis_adapter,
        "predict_primary_module",
        lambda *args, **kwargs: (np.asarray([0.4]), np.asarray([0.2])),
    )

    result = anfis_adapter.fit_primary_module(
        selected,
        runtime=_runtime(),
        gate=_gate(("A",)),
        module="ANFIS-T-no-current",
        module_seed=2133,
    )

    assert events[:2] == ["seed:2133", "construct"]
    assert result.metrics["curve_last_pre_update_loss"] == pytest.approx(0.1)
    assert result.metrics["final_checkpoint_loss"] == pytest.approx(0.05)
    assert result.metrics["quality_gate_output_standard_deviation"] == pytest.approx(0.02)
    assert result.metrics["quality_gate_output_scope"] == (
        "locked_hash_ranked_training_sample_4096"
    )


def test_post_update_anchor_metrics_evaluate_checkpoint_predictions() -> None:
    torch = anfis_adapter._require_torch()

    class FixedModel(torch.nn.Module):
        def forward(self, values: Any) -> Any:
            return values[:, 0]

    loss, output_std = anfis_adapter._post_update_anchor_metrics(
        FixedModel(),
        np.asarray([[0.0], [1.0]], dtype="float32"),
        np.asarray([0.5, 0.5], dtype="float32"),
    )

    assert loss == pytest.approx(0.25)
    assert output_std == pytest.approx(0.5)


def test_quality_gate_uses_training_sample_spread_not_later_surface_variance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = pd.DataFrame(
        [{**_roles("A"), "temp_favorable": 0.5, "yT_no_chla": 0.6}]
    )
    surface = pd.concat(
        [
            selected,
            selected.assign(
                year_month="2021-01",
                time_role="calibration_threshold",
            ),
        ],
        ignore_index=True,
    )

    class FakeModel:
        rule_count = 3

        def parameters(self) -> list[Any]:
            return []

        def ordered_centers(self) -> Any:
            return anfis_adapter._require_torch().tensor([[0.1, 0.5, 0.9]])

        def positive_widths(self) -> Any:
            return anfis_adapter._require_torch().tensor([[0.2, 0.2, 0.2]])

        def centers_are_ordered(self) -> bool:
            return True

        def centers_in_unit_interval(self) -> bool:
            return True

    monkeypatch.setattr(
        anfis_adapter,
        "select_module_training_rows",
        lambda *args, **kwargs: (
            selected,
            pd.DataFrame(
                [{"source_id": "wqp", "site_id": "A", "year_month": "2018-01"}]
            ),
            {"base_seed": 1729, "selected_rows": 1},
        ),
    )
    monkeypatch.setattr(anfis_adapter, "set_closure_anfis_seed", lambda seed: None)
    monkeypatch.setattr(anfis_adapter, "make_adaptive_anfis", lambda **kwargs: FakeModel())
    monkeypatch.setattr(anfis_adapter, "parameter_snapshot", lambda model: {})
    monkeypatch.setattr(anfis_adapter, "max_parameter_delta", lambda *args: 1.0)
    monkeypatch.setattr(
        anfis_adapter,
        "train_supervised_anfis",
        lambda *args, **kwargs: [{"epoch": 1.0, "loss": 0.1}],
    )
    monkeypatch.setattr(
        anfis_adapter,
        "_post_update_anchor_metrics",
        lambda *args, **kwargs: (0.05, 0.0),
    )
    monkeypatch.setattr(
        anfis_adapter,
        "predict_primary_module",
        lambda *args, **kwargs: (np.asarray([0.0, 1.0]), np.asarray([0.2, 0.2])),
    )

    result = anfis_adapter.fit_primary_module(
        surface,
        runtime=_runtime(),
        gate=_gate(("A",)),
        module="ANFIS-T-no-current",
        module_seed=2133,
    )

    assert result.metrics["status"] == "failed"
    assert result.metrics["quality_gate_output_standard_deviation"] == 0.0
    assert result.metrics["materialized_surface_output_standard_deviation"] == pytest.approx(
        0.5
    )


def test_programmatic_materializer_authorizes_before_runtime_or_parquet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    def blocked(**kwargs: Any) -> dict[str, Any]:
        events.append("authorize")
        raise ClosureRuntimeContractError("E0-DL is absent")

    monkeypatch.setattr(anfis_adapter, "authorize_development_fit", blocked)
    monkeypatch.setattr(
        anfis_adapter,
        "load_and_validate_development_runtime",
        lambda *args, **kwargs: (events.append("runtime") or None),
    )
    monkeypatch.setattr(
        anfis_adapter,
        "load_joined_anfis_surface",
        lambda **kwargs: (events.append("parquet") or None),
    )

    with pytest.raises(ClosureRuntimeContractError, match="E0-DL"):
        anfis_adapter.materialize_anfis_seed_slot(base_seed=1729)
    assert events == ["authorize"]


def test_materializer_api_rejects_spoofed_authorization_mapping_before_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    monkeypatch.setattr(
        anfis_adapter,
        "authorize_development_fit",
        lambda **kwargs: (events.append("authorize") or {}),
    )
    monkeypatch.setattr(
        anfis_adapter,
        "load_joined_anfis_surface",
        lambda **kwargs: (events.append("parquet") or None),
    )

    spoof_attempt: Any = anfis_adapter.materialize_anfis_seed_slot
    with pytest.raises(TypeError, match="authorization"):
        spoof_attempt(
            base_seed=1729,
            runtime_config=Path("runtime.yaml"),
            runtime_schema=Path("runtime.schema.json"),
            authorization={},
        )
    assert events == []


def test_slot_bundle_writes_completion_manifest_last(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, Path]] = []
    paths: dict[str, Any] = {
        "anfis_state_template": tmp_path / "state.parquet",
        "anfis_metrics_template": tmp_path / "metrics.csv",
        "anfis_training_curve_template": tmp_path / "curve.csv",
        "anfis_memberships_initial_template": tmp_path / "initial.csv",
        "anfis_memberships_final_template": tmp_path / "final.csv",
        "anfis_report_template": tmp_path / "report.md",
        "anfis_manifest_template": tmp_path / "manifest.json",
        "anfis_lineage_audit_template": tmp_path / "lineage.json",
        "models": {module: tmp_path / f"{module}.pt" for module in anfis_adapter.PRIMARY_MODULES},
        "samples": {module: tmp_path / f"{module}.csv" for module in anfis_adapter.PRIMARY_MODULES},
    }

    class FakeModel:
        def state_dict(self) -> dict[str, Any]:
            return {}

    results: dict[str, anfis_adapter.ModuleFitResult] = {}
    for module in anfis_adapter.PRIMARY_MODULES:
        result = _dummy_result(module, [0.5], [0.2])
        result.model = FakeModel()
        result.module_seed = 1
        result.sample_audit = {"base_seed": 1729}
        result.sample_keys = pd.DataFrame({"site_id": ["A"]})
        result.metrics = {
            "module": module,
            "status": "passed",
            "train_rows": 1,
            "final_checkpoint_loss": 0.1,
            "quality_gate_output_standard_deviation": 0.01,
        }
        result.curve = pd.DataFrame({"module": [module], "loss": [0.1]})
        result.memberships_initial = pd.DataFrame({"module": [module]})
        result.memberships_final = pd.DataFrame({"module": [module]})
        results[module] = result

    monkeypatch.setattr(anfis_adapter, "_slot_paths", lambda runtime, base_seed: paths)
    monkeypatch.setattr(
        anfis_adapter,
        "_write_parquet_atomic",
        lambda frame, path: calls.append(("parquet", path)),
    )
    monkeypatch.setattr(
        anfis_adapter,
        "_torch_save_atomic",
        lambda payload, path: calls.append(("torch", path)),
    )
    monkeypatch.setattr(
        anfis_adapter,
        "_write_csv_atomic",
        lambda frame, path: calls.append(("csv", path)),
    )
    monkeypatch.setattr(
        anfis_adapter,
        "_write_text_atomic",
        lambda text, path: calls.append(("text", path)),
    )
    monkeypatch.setattr(
        anfis_adapter,
        "_write_json_atomic",
        lambda payload, path: calls.append(("json", path)),
    )
    monkeypatch.setattr(
        anfis_adapter,
        "_file_record",
        lambda path: {"path": path.as_posix(), "bytes": 1, "sha256": "a" * 64},
    )
    state = pd.DataFrame(
        {
            "source_id": ["wqp"],
            "site_id": ["A"],
            "year_month": ["2018-01"],
            "delta_previous_month_missing": [True],
        }
    )
    audit = DevelopmentScanAudit(1, 1, 0, (("training", 1),))

    payload = anfis_adapter.write_anfis_slot_bundle(
        state,
        results,
        runtime=_runtime(),
        base_seed=1729,
        join_audits=_join_audits(
            anfis_adapter.PanelAnchorJoinAudit(1, 1, 1, 0, 0, "a", "b", "c", "d", "e")
        ),
        scan_audits={"panel": audit, "expert_anchor": audit},
        manifest_base={"status": "pending"},
    )

    assert calls[-1] == ("json", paths["anfis_manifest_template"])
    assert calls[-2] == ("json", paths["anfis_lineage_audit_template"])
    assert payload["status"] == "completed"
    assert payload["slot_status"] == "available"
    assert payload["fit_status"] == "passed"
    assert payload["state_artifact_emitted"] is True
    assert payload["state_output_materialized"] is True
    assert payload["checkpoint_outputs_materialized"] is True
    assert payload["model_construction_attempted"] is True
    assert payload["fit_attempted"] is True
    assert payload["replacement_used"] is False
    assert payload["failed_slot_replaced"] is False
    state_record = next(
        record for record in payload["outputs"] if record["role"] == "adaptive_no_current_state"
    )
    assert state_record == {
        "path": paths["anfis_state_template"].as_posix(),
        "bytes": 1,
        "sha256": "a" * 64,
        "role": "adaptive_no_current_state",
    }


def _test_slot_paths(tmp_path: Path) -> dict[str, Any]:
    return {
        "anfis_state_template": tmp_path / "state.parquet",
        "anfis_metrics_template": tmp_path / "metrics.csv",
        "anfis_training_curve_template": tmp_path / "curve.csv",
        "anfis_memberships_initial_template": tmp_path / "initial.csv",
        "anfis_memberships_final_template": tmp_path / "final.csv",
        "anfis_report_template": tmp_path / "report.md",
        "anfis_manifest_template": tmp_path / "manifest.json",
        "anfis_lineage_audit_template": tmp_path / "lineage.json",
        "models": {
            module: tmp_path / f"{module}.pt" for module in anfis_adapter.PRIMARY_MODULES
        },
        "samples": {
            module: tmp_path / f"{module}.csv" for module in anfis_adapter.PRIMARY_MODULES
        },
    }


def test_materializer_retains_unavailable_slot_without_fit_or_heavy_outputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime()
    paths = _test_slot_paths(tmp_path)
    surface = _small_all_module_surface()
    scan = DevelopmentScanAudit(2, 2, 0, (("training", 2),))
    join = anfis_adapter.PanelAnchorJoinAudit(2, 2, 2, 0, 0, "a", "b", "c", "d", "e")
    monkeypatch.setattr(
        anfis_adapter,
        "load_and_validate_development_runtime",
        lambda config, schema, **kwargs: (
            runtime,
            {
                "config_path": "configs/runtime.yaml",
                "config_sha256": "a" * 64,
                "schema_path": "configs/runtime.schema.json",
                "schema_sha256": "b" * 64,
            },
        ),
    )
    monkeypatch.setattr(anfis_adapter, "authorize_development_fit", lambda **kwargs: {})
    monkeypatch.setattr(
        anfis_adapter,
        "configure_torch_cpu_execution_policy",
        lambda runtime: {"torch_num_threads_observed": 1},
    )
    monkeypatch.setattr(anfis_adapter, "_validate_authorization", lambda *args, **kwargs: None)
    monkeypatch.setattr(anfis_adapter, "load_development_gate", lambda: _gate(("A", "B")))
    monkeypatch.setattr(
        anfis_adapter,
        "anfis_dependency_paths_and_roles",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        anfis_adapter,
        "_validate_restored_dependency_snapshot",
        lambda *args: None,
    )
    monkeypatch.setattr(
        anfis_adapter,
        "load_joined_anfis_surface",
        lambda **kwargs: anfis_adapter.AnfisSurfaceViews(
            full_development=surface,
            training_candidates=surface,
            full_development_join=join,
            training_candidate_join=join,
            source_scans={"panel": scan, "expert_anchor": scan},
        ),
    )
    monkeypatch.setattr(anfis_adapter, "_slot_paths", lambda runtime, base_seed: paths)
    monkeypatch.setattr(
        anfis_adapter,
        "fit_primary_module",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("fit attempted")),
    )
    monkeypatch.setattr(
        anfis_adapter,
        "build_adaptive_state",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("state built")),
    )

    payload = anfis_adapter.materialize_anfis_seed_slot(
        base_seed=1729,
    )

    assert payload["status"] == "completed"
    assert payload["slot_status"] == "model_unavailable"
    assert payload["fit_status"] == "not_attempted"
    assert payload["model_id"] == "F1"
    assert payload["consumer_model_id"] == "P1"
    assert payload["failure_reason"] == "insufficient_eligible_training_rows"
    assert payload["retain_failed_seed_slot"] is True
    assert payload["replacement_used"] is False
    assert payload["model_construction_attempted"] is False
    assert payload["fit_attempted"] is False
    assert payload["state_output_materialized"] is False
    assert payload["state_artifact_emitted"] is False
    assert payload["checkpoint_outputs_materialized"] is False
    assert payload["failed_slot_replaced"] is False
    assert payload["failed_modules"] == list(anfis_adapter.PRIMARY_MODULES)
    assert paths["anfis_manifest_template"].is_file()
    assert paths["anfis_lineage_audit_template"].is_file()
    assert not paths["anfis_state_template"].exists()
    assert all(not path.exists() for path in paths["models"].values())
    assert all(
        not record["path"].endswith((".parquet", ".pt")) for record in payload["outputs"]
    )


def test_materializer_rejects_existing_seed_artifact_before_rows_or_model(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime()
    paths = _test_slot_paths(tmp_path)
    monkeypatch.setattr(anfis_adapter, "_slot_paths", lambda *args: paths)
    pointer = paths["anfis_state_template"].with_suffix(".parquet.dvc")
    for stale_path in (paths["anfis_manifest_template"], pointer):
        stale_path.write_text("stale\n", encoding="utf-8")
        with pytest.raises(ClosureRuntimeContractError, match="one-shot"):
            anfis_adapter.require_pristine_anfis_seed_slot(runtime, 1729)
        stale_path.unlink()

    pointer.write_text("stale pointer\n", encoding="utf-8")
    events: list[str] = []
    monkeypatch.setattr(
        anfis_adapter,
        "load_and_validate_development_runtime",
        lambda *args, **kwargs: (
            runtime,
            {
                "config_path": "configs/runtime.yaml",
                "config_sha256": "a" * 64,
                "schema_path": "configs/runtime.schema.json",
                "schema_sha256": "b" * 64,
            },
        ),
    )
    monkeypatch.setattr(anfis_adapter, "authorize_development_fit", lambda **kwargs: {})
    monkeypatch.setattr(anfis_adapter, "_validate_authorization", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        anfis_adapter,
        "configure_torch_cpu_execution_policy",
        lambda runtime: {"torch_num_threads_observed": 1},
    )
    monkeypatch.setattr(anfis_adapter, "load_development_gate", lambda: _gate(("A",)))
    monkeypatch.setattr(
        anfis_adapter,
        "anfis_dependency_paths_and_roles",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        anfis_adapter,
        "_validate_restored_dependency_snapshot",
        lambda *args: None,
    )
    monkeypatch.setattr(
        anfis_adapter,
        "load_joined_anfis_surface",
        lambda **kwargs: events.append("row_io"),
    )
    monkeypatch.setattr(
        anfis_adapter,
        "make_adaptive_anfis",
        lambda **kwargs: events.append("model"),
    )

    with pytest.raises(ClosureRuntimeContractError, match="one-shot"):
        anfis_adapter.materialize_anfis_seed_slot(base_seed=1729)
    assert events == []


def test_anfis_dependency_contract_has_exact_unique_role_bearing_records() -> None:
    dependencies = anfis_adapter.anfis_dependency_paths_and_roles(
        runtime=_runtime(),
        runtime_config=Path("configs/closure_v1/development_runtime.yaml"),
        runtime_schema=Path("configs/closure_v1/development_runtime.schema.json"),
        gate=_gate(("A",)),
    )

    roles = [role for _, role in dependencies]
    assert roles == [
        "development_runtime_config",
        "development_runtime_schema",
        "development_runtime_lock",
        "development_runtime_lock_schema",
        "common_origin",
        "common_origin_completion_manifest",
        "restored_panel",
        "restored_expert_anchor",
        "holdout_assignment",
        "holdout_manifest",
        "protocol_lock",
        "strict_anfis_state_adapter",
        "strict_expert_state_adapter",
        "runtime_lock_validator",
        "runtime_contract_validator",
        "closure_development_guard",
        "closure_contract",
        "adaptive_anfis_implementation",
    ]
    assert len({path.resolve() for path, _ in dependencies}) == len(dependencies)


def test_restored_dependency_snapshot_is_bound_to_locked_source_hashes() -> None:
    runtime = _runtime()
    projection = runtime["anfis"]["source_projection"]
    panel = str(projection["panel_path"])
    anchor = str(projection["expert_anchor_path"])
    before = {
        panel: {"sha256": anfis_adapter.EXPECTED_PANEL_SHA256},
        anchor: {"sha256": anfis_adapter.EXPECTED_EXPERT_STATE_SHA256},
    }

    anfis_adapter._validate_restored_dependency_snapshot(before, runtime)
    before[panel]["sha256"] = "f" * 64
    with pytest.raises(ClosureRuntimeContractError, match="panel changed"):
        anfis_adapter._validate_restored_dependency_snapshot(before, runtime)


def test_unavailable_bundle_writes_manifest_last_and_refuses_stale_fit_outputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = _test_slot_paths(tmp_path)
    calls: list[tuple[str, Path]] = []
    unavailable = {
        module: anfis_adapter.ModuleSamplingUnavailable(
            module=module,
            module_seed=seed,
            base_seed=1729,
            required_rows=4096,
            eligible_rows=2,
            audit={
                "input_rows": 2,
                "excluded_nonfinite_target_rows": 0,
                "excluded_missingness_rows": 0,
                "eligible_universe_rows": 2,
                "eligible_universe_sha256": "a" * 64,
                "selected_rows": 0,
                "selected_keys_sha256": "b" * 64,
                "module": module,
                "base_seed": 1729,
                "module_seed": seed,
                "required_rows": 4096,
                "replacement_used": False,
                "failure_reason": "insufficient_eligible_training_rows",
            },
        )
        for module, seed in anfis_adapter.anfis_module_substreams(1729).items()
    }
    monkeypatch.setattr(anfis_adapter, "_slot_paths", lambda runtime, base_seed: paths)
    monkeypatch.setattr(
        anfis_adapter,
        "_write_csv_atomic",
        lambda frame, path: calls.append(("csv", path)),
    )
    monkeypatch.setattr(
        anfis_adapter,
        "_write_text_atomic",
        lambda text, path: calls.append(("text", path)),
    )
    monkeypatch.setattr(
        anfis_adapter,
        "_write_json_atomic",
        lambda payload, path: calls.append(("json", path)),
    )
    monkeypatch.setattr(
        anfis_adapter,
        "_file_record",
        lambda path: {"path": path.as_posix(), "bytes": 1, "sha256": "a" * 64},
    )
    scan = DevelopmentScanAudit(2, 2, 0, (("training", 2),))
    payload = anfis_adapter.write_anfis_unavailable_slot_bundle(
        {},
        unavailable,
        runtime=_runtime(),
        base_seed=1729,
        join_audits=_join_audits(
            anfis_adapter.PanelAnchorJoinAudit(2, 2, 2, 0, 0, "a", "b", "c", "d", "e")
        ),
        scan_audits={"panel": scan, "expert_anchor": scan},
        manifest_base={"completion_marker_written_last": True},
    )

    assert payload["status"] == "completed"
    assert payload["fit_status"] == "not_attempted"
    assert calls[-1] == ("json", paths["anfis_manifest_template"])
    assert not any(kind in {"parquet", "torch"} for kind, _ in calls)

    paths["anfis_state_template"].write_bytes(b"stale")
    with pytest.raises(
        ClosureRuntimeContractError,
        match="pre-existing state/checkpoint/fit-only",
    ):
        anfis_adapter.write_anfis_unavailable_slot_bundle(
            {},
            unavailable,
            runtime=_runtime(),
            base_seed=1729,
            join_audits=_join_audits(
                anfis_adapter.PanelAnchorJoinAudit(
                    2, 2, 2, 0, 0, "a", "b", "c", "d", "e"
                )
            ),
            scan_audits={"panel": scan, "expert_anchor": scan},
            manifest_base={},
        )
    paths["anfis_state_template"].unlink()

    for field in (
        "anfis_training_curve_template",
        "anfis_memberships_initial_template",
        "anfis_memberships_final_template",
    ):
        stale_path = paths[field]
        stale_path.write_text("stale\n", encoding="utf-8")
        with pytest.raises(
            ClosureRuntimeContractError,
            match="pre-existing state/checkpoint/fit-only",
        ):
            anfis_adapter.write_anfis_unavailable_slot_bundle(
                {},
                unavailable,
                runtime=_runtime(),
                base_seed=1729,
                join_audits=_join_audits(
                    anfis_adapter.PanelAnchorJoinAudit(
                        2, 2, 2, 0, 0, "a", "b", "c", "d", "e"
                    )
                ),
                scan_audits={"panel": scan, "expert_anchor": scan},
                manifest_base={},
            )
        stale_path.unlink()
