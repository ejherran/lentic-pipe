from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pytest

from src.experiments import fit_closure_baselines as baseline


def _common(origins: list[tuple[str, str]]) -> pd.DataFrame:
    rows = []
    for index, (origin, role) in enumerate(origins):
        for horizon in baseline.HORIZONS:
            origin_year, origin_month = (int(value) for value in origin.split("-"))
            shifted = origin_year * 12 + origin_month - 1 + horizon
            target = f"{shifted // 12:04d}-{shifted % 12 + 1:02d}"
            rows.append(
                {
                    "source_id": "wqp",
                    "site_id": "site-a",
                    "common_origin_id": f"origin-{index}",
                    "evaluation_unit_id": f"eval-{index}-{horizon}",
                    "holdout_group_id": "wqp:site-a",
                    "assignment_role": "development",
                    "time_role": role,
                    "origin_year_month": origin,
                    "target_year_month": target,
                    "horizon_months": horizon,
                    "input_eligible": True,
                    "target_evaluable": True,
                    "complete_targets_evaluable": True,
                }
            )
    return pd.DataFrame(rows)


def _targets(common: pd.DataFrame) -> pd.DataFrame:
    frame = common[baseline.TARGET_JOIN_COLUMNS].copy()
    frame["has_target"] = True
    frame["bloom_h"] = (frame["origin_year_month"].str[-2:].astype(int) % 2).astype(bool)
    frame["target_risk_chla_h"] = np.where(frame["bloom_h"], 0.8, 0.2)
    return frame


def test_runtime_is_closed_and_features_match_model_benchmark() -> None:
    contract = baseline.load_runtime_contract()
    assert contract["gate"] == "E0-MP"
    assert contract["authorizations"]["baseline_one_shot_authorized"] is False
    assert contract["authorizations"]["outcome_access_log_required_state"] == "absent"
    assert contract["outputs"]["minimum_final_path_count"] == 39
    assert contract["outputs"]["maximum_final_path_count"] == 69
    assert contract["outputs"]["raw_prediction_contract"] == (
        baseline.raw_prediction_contract()
    )
    assert baseline.exact_feature_columns(contract) == (
        contract["models"]["B2"]["physical_feature_columns"]
        + contract["models"]["B2"]["derived_calendar_columns"]
    )


def test_calendar_features_use_one_based_closed_formula_and_float32() -> None:
    frame = baseline.derive_calendar_features(pd.Series(["2020-01", "2020-04", "2020-07"]))
    assert all(dtype == np.dtype("float32") for dtype in frame.dtypes)
    assert frame.loc[0, "season_sin_annual"] == pytest.approx(0.0, abs=1e-7)
    assert frame.loc[0, "season_cos_annual"] == pytest.approx(1.0, abs=1e-7)
    assert frame.loc[1, "season_sin_annual"] == pytest.approx(1.0, abs=1e-7)
    assert frame.loc[2, "season_cos_annual"] == pytest.approx(-1.0, abs=1e-7)


def test_calendar_features_reject_invalid_month() -> None:
    with pytest.raises(baseline.BaselineDevelopmentError, match="Invalid YYYY-MM"):
        baseline.derive_calendar_features(pd.Series(["2020-13"]))


def test_b1_formula_is_no_chla_equal_weight_and_retains_missing() -> None:
    frame = pd.DataFrame(
        {
            "yN_adaptive": [0.8, np.nan, 2.0],
            "yF_adaptive": [0.2, 0.2, 0.0],
            "yT_no_chla_adaptive": [0.5, 0.5, 2.0],
        }
    )
    result = baseline.derive_b1_score(frame)
    assert result.iloc[0] == pytest.approx((0.8 + 0.8 + 0.5) / 3.0)
    assert np.isnan(result.iloc[1])
    assert result.iloc[2] == 1.0


def test_b0_uses_training_targets_and_predicts_every_intent_row() -> None:
    common = _common(
        [
            ("2018-01", "training"),
            ("2018-02", "training"),
            ("2019-01", "model_selection"),
        ]
    )
    targets = _targets(common)
    targets.loc[targets["origin_year_month"].eq("2019-01"), "bloom_h"] = True
    result, prevalence = baseline.build_b0_predictions(common, targets)
    assert len(result) == len(common)
    assert prevalence == {"1": 0.5, "2": 0.5, "3": 0.5}
    assert result["predicted_bloom_probability"].eq(0.5).all()


def test_b1_keeps_five_upstream_seeds_without_fallback() -> None:
    common = _common([("2018-01", "training"), ("2019-01", "model_selection")])
    state_by_seed = {}
    for seed in baseline.MODEL_SEEDS:
        state_by_seed[seed] = pd.DataFrame(
            {
                "source_id": ["wqp"],
                "site_id": ["site-a"],
                "year_month": ["2018-01"],
                "yN_adaptive": [0.8],
                "yF_adaptive": [0.2],
                "yT_no_chla_adaptive": [0.5],
            }
        )
    result = baseline.build_b1_predictions(common, state_by_seed)
    assert len(result) == len(common) * 5
    assert set(result["upstream_state_seed"].astype(int)) == set(baseline.MODEL_SEEDS)
    available = result["availability_status"].eq("success")
    assert result.loc[available, "predicted_bloom_probability"].equals(
        result.loc[available, "raw_score"]
    )
    assert result.loc[available, "score_semantics"].eq(
        "uncalibrated_chla_free_irc_persistence_probability"
    ).all()
    missing = result["origin_year_month"].eq("2019-01")
    assert result.loc[missing, "availability_status"].eq("model_unavailable").all()
    assert result.loc[missing, "failure_reason"].eq("chla_free_origin_state_unavailable").all()
    table = baseline.raw_prediction_arrow_table(result)
    assert table.column_names == list(baseline.RAW_PREDICTION_COLUMNS)
    assert table.schema.field("horizon_months").type == pa.int16()
    assert table.schema.field("upstream_state_seed").type == pa.int64()
    assert table.schema.field("raw_score").type == pa.float64()
    assert table.schema.field("predicted_bloom_probability").type == pa.float64()
    assert table.column("raw_score").null_count == int(missing.sum())
    assert table.column("predicted_bloom_probability").null_count == int(missing.sum())
    declared = baseline.raw_prediction_contract()
    assert [record["name"] for record in declared["columns"]] == list(
        baseline.RAW_PREDICTION_COLUMNS
    )
    arrow_types = {
        "string": pa.string(),
        "int16": pa.int16(),
        "int64": pa.int64(),
        "bool": pa.bool_(),
        "float64": pa.float64(),
    }
    assert [field.type for field in table.schema] == [
        arrow_types[record["dtype"]] for record in declared["columns"]
    ]


def test_b1_bloom_metrics_do_not_depend_on_continuous_target_availability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    common = _common(
        [
            ("2018-01", "training"),
            ("2018-02", "training"),
            ("2019-01", "model_selection"),
            ("2019-02", "model_selection"),
        ]
    )
    targets = _targets(common)
    b0, _ = baseline.build_b0_predictions(common, targets)
    states = {
        seed: pd.DataFrame(
            {
                "source_id": ["wqp"] * 4,
                "site_id": ["site-a"] * 4,
                "year_month": ["2018-01", "2018-02", "2019-01", "2019-02"],
                "yN_adaptive": [0.1, 0.9, 0.1, 0.9],
                "yF_adaptive": [0.9, 0.1, 0.9, 0.1],
                "yT_no_chla_adaptive": [0.1, 0.9, 0.1, 0.9],
            }
        )
        for seed in baseline.MODEL_SEEDS
    }
    b1 = baseline.build_b1_predictions(common, states)
    targets.loc[
        targets["origin_year_month"].str.startswith("2019"),
        "target_risk_chla_h",
    ] = np.nan
    monkeypatch.setattr(
        baseline,
        "EXPECTED_COMPLETE_ORIGINS",
        {
            **baseline.EXPECTED_COMPLETE_ORIGINS,
            "model_selection": 2,
        },
    )
    metrics = baseline._score_b0_b1_metrics(b0, b1, common, targets)
    b1_metrics = metrics.loc[metrics["model_id"].eq("B1")]
    assert b1_metrics["technical_seed"].eq(baseline.TECHNICAL_SEED).all()
    assert b1_metrics["model_seed"].isna().all()
    assert set(b1_metrics["upstream_state_seed"].astype(int)) == set(
        baseline.MODEL_SEEDS
    )
    assert np.isfinite(b1_metrics["brier"]).all()
    assert np.isfinite(b1_metrics["pr_auc"]).all()
    assert b1_metrics["continuous_rows"].eq(0).all()
    assert b1_metrics["rmse"].isna().all()


def _selection_metrics(*, logistic_brier: float, hgb_brier: float, logistic_pr: float, hgb_pr: float) -> pd.DataFrame:
    rows = []
    for horizon in baseline.HORIZONS:
        for seed in baseline.MODEL_SEEDS:
            rows.extend(
                [
                    {
                        "candidate": "logistic_sgd",
                        "model_seed": seed,
                        "horizon_months": horizon,
                        "brier": logistic_brier,
                        "pr_auc": logistic_pr,
                        "fit_status": "success",
                    },
                    {
                        "candidate": "hist_gradient_boosting_classifier",
                        "model_seed": seed,
                        "horizon_months": horizon,
                        "brier": hgb_brier,
                        "pr_auc": hgb_pr,
                        "fit_status": "success",
                    },
                ]
            )
    return pd.DataFrame(rows)


def test_b2_selection_uses_brier_tolerance_then_pr_auc() -> None:
    metrics = _selection_metrics(
        logistic_brier=0.2008,
        hgb_brier=0.2000,
        logistic_pr=0.7,
        hgb_pr=0.6,
    )
    selected = baseline.select_b2_families(metrics)
    assert selected["selected_candidate"].eq("logistic_sgd").all()


def test_b2_selection_uses_logistic_as_final_tie_break() -> None:
    metrics = _selection_metrics(
        logistic_brier=0.2,
        hgb_brier=0.2,
        logistic_pr=0.7,
        hgb_pr=0.7,
    )
    selected = baseline.select_b2_families(metrics)
    assert selected["selected_candidate"].eq("logistic_sgd").all()


def test_b2_selection_requires_five_finite_seeds() -> None:
    metrics = _selection_metrics(
        logistic_brier=0.2,
        hgb_brier=0.3,
        logistic_pr=0.7,
        hgb_pr=0.6,
    )
    metrics = metrics.loc[
        ~(
            metrics["candidate"].eq("logistic_sgd")
            & metrics["model_seed"].eq(baseline.MODEL_SEEDS[-1])
        )
    ]
    selected = baseline.select_b2_families(metrics)
    assert selected["selected_candidate"].eq("hist_gradient_boosting_classifier").all()


def test_unavailable_selection_serializes_as_strict_json_null() -> None:
    metrics = _selection_metrics(
        logistic_brier=0.2,
        hgb_brier=0.3,
        logistic_pr=0.7,
        hgb_pr=0.6,
    )
    metrics["fit_status"] = "model_unavailable"
    metrics[["brier", "pr_auc"]] = np.nan
    selected = baseline.select_b2_families(metrics)
    payload = baseline._canonical_json_bytes({"selection": baseline._json_records(selected)})
    assert b'"selected_candidate":null' in payload
    assert b"NaN" not in payload
    manifest = baseline._manifest_json_bytes(
        {"status": "completed", "completion_marker_written_last": True}
    )
    assert manifest.endswith(b'"completion_marker_written_last":true}\n')


def test_preprocessor_rejects_all_missing_training_feature() -> None:
    frame = pd.DataFrame({"a": [1.0, 2.0], "b": [np.nan, np.inf]})
    with pytest.raises(baseline.BaselineDevelopmentError, match="no finite values"):
        baseline._fit_preprocessor(frame, ["a", "b"], scale=True)


def test_preprocessor_normalizes_nonfinite_and_preserves_order() -> None:
    frame = pd.DataFrame({"b": [1.0, np.inf, 3.0], "a": [2.0, 4.0, 6.0]})
    matrix, payload = baseline._fit_preprocessor(frame, ["a", "b"], scale=False)
    assert payload["feature_order"] == ["a", "b"]
    assert payload["finite_training_counts"] == [3, 2]
    assert matrix[1, 1] == 2.0
    assert np.isfinite(matrix).all()


def test_b2_fit_failure_keeps_all_candidate_rows_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    common = _common(
        [
            ("2018-01", "training"),
            ("2018-02", "training"),
            ("2019-01", "model_selection"),
            ("2019-02", "model_selection"),
        ]
    )
    targets = _targets(common)
    contract = baseline.load_runtime_contract()
    features = baseline.exact_feature_columns(contract)
    panel = pd.DataFrame(
        {
            "source_id": ["wqp"] * 4,
            "site_id": ["site-a"] * 4,
            "origin_year_month": ["2018-01", "2018-02", "2019-01", "2019-02"],
            **{feature: [1.0, 2.0, 3.0, 4.0] for feature in features},
        }
    )

    class FailingClassifier:
        def __init__(self, **kwargs: object) -> None:
            pass

        def fit(self, matrix: np.ndarray, labels: np.ndarray) -> None:
            raise ValueError("injected fit failure")

    monkeypatch.setattr(
        baseline,
        "EXPECTED_COMPLETE_ORIGINS",
        {"training": 2, "model_selection": 2, "calibration_threshold": 0},
    )
    monkeypatch.setattr(baseline, "SGDClassifier", FailingClassifier)
    monkeypatch.setattr(baseline, "HistGradientBoostingClassifier", FailingClassifier)
    raw, metrics, models, preprocessors = baseline.fit_b2(
        common,
        targets,
        panel,
        contract,
    )
    assert models == {}
    assert len(preprocessors) == 30
    assert metrics["fit_status"].eq("model_unavailable").all()
    assert raw["availability_status"].eq("model_unavailable").all()
    assert raw["raw_score"].isna().all()
    assert raw["predicted_bloom_probability"].isna().all()


def test_target_reader_pushes_2020_cutoff_into_arrow_scanner(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}
    table = pa.Table.from_pydict(
        {
            "source_id": ["wqp"],
            "site_id": ["site-a"],
            "origin_year_month": ["2020-11"],
            "target_year_month": ["2020-12"],
            "horizon_months": [1],
            "has_target": [True],
            "bloom_h": [False],
            "target_risk_chla_h": [0.2],
        }
    )

    class FakeScanner:
        def to_table(self) -> pa.Table:
            return table

    class FakeDataset:
        def scanner(self, *, columns, filter):  # noqa: A002
            captured["columns"] = columns
            captured["filter"] = str(filter)
            return FakeScanner()

    monkeypatch.setattr(baseline.ds, "dataset", lambda *args, **kwargs: FakeDataset())
    result = baseline._target_frame(["site-a"])
    assert len(result) == 1
    assert "2020-12" in captured["filter"]
    assert captured["columns"] == baseline.TARGET_JOIN_COLUMNS + [
        "bloom_h",
        "target_risk_chla_h",
    ]


def test_declared_output_namespace_has_exactly_69_finals() -> None:
    contract = baseline.load_runtime_contract()
    paths, manifest = baseline._output_paths(contract)
    assert len(paths) + 1 == 69
    assert len(set(paths + [manifest])) == 69


def test_cli_is_closed() -> None:
    assert baseline.parse_args(["--check-only"]).check_only is True
    assert baseline.parse_args(["--execute-one-shot"]).execute_one_shot is True
    with pytest.raises(SystemExit):
        baseline.parse_args([])
    with pytest.raises(SystemExit):
        baseline.parse_args(["--check-only", "--execute-one-shot"])
    with pytest.raises(SystemExit):
        baseline.parse_args(["--check-only", "--output", "elsewhere"])


def _effective_authority() -> dict[str, object]:
    return {
        "gate": "E0-MQ",
        "status": "effective_preflight_passed",
        "baseline_one_shot_authorized": True,
        "b0_fit_authorized": True,
        "b1_execution_authorized": True,
        "b2_fit_authorized": True,
        "calibration_authorized": False,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "dvc_commands_authorized": False,
        "network_authorized": False,
        "outcome_access_authorized": False,
        "future_outcomes_accessed": False,
        "development_target_access_end": "2020-12",
        "target_projection": list(baseline.TARGET_PROJECTION),
        "h_patch_head": "1" * 40,
        "p_patch_head": "2" * 40,
        "lock_sha256": "3" * 64,
        "companion_sha256": "4" * 64,
        "runtime_sha256": "5" * 64,
        "h_components_sha256": "6" * 64,
        "physical_inputs_sha256": "7" * 64,
        "runner_sha256": "8" * 64,
    }


def test_effective_authority_requires_all_four_scoped_permissions_and_bindings() -> None:
    expected = _effective_authority()
    assert baseline._validated_authority_snapshot(expected) == expected
    for name in (
        "baseline_one_shot_authorized",
        "b0_fit_authorized",
        "b1_execution_authorized",
        "b2_fit_authorized",
    ):
        altered = dict(expected)
        altered[name] = False
        with pytest.raises(baseline.BaselineDevelopmentError, match="incomplete"):
            baseline._validated_authority_snapshot(altered)
    altered = dict(expected)
    altered["companion_sha256"] = "bad"
    with pytest.raises(baseline.BaselineDevelopmentError, match="hash binding"):
        baseline._validated_authority_snapshot(altered)


def test_authority_is_first_operation_after_parse_args() -> None:
    source = Path(baseline.__file__).read_text(encoding="utf-8")
    module = ast.parse(source)
    main = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    assert isinstance(main.body[0], ast.Assign)
    assert isinstance(main.body[0].value, ast.Call)
    assert getattr(main.body[0].value.func, "id", "") == "parse_args"
    assert isinstance(main.body[1], ast.Assign)
    assert isinstance(main.body[1].value, ast.Call)
    assert getattr(main.body[1].value.func, "id", "") == "_require_effective_authority"


def test_importable_preflight_and_execute_cannot_bypass_effective_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = Path(baseline.__file__).read_text(encoding="utf-8")
    module = ast.parse(source)
    for function_name in ("preflight", "execute_one_shot"):
        function = next(
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name == function_name
        )
        assert isinstance(function.body[0], ast.Assign)
        assert isinstance(function.body[0].value, ast.Call)
        assert (
            getattr(function.body[0].value.func, "id", "")
            == "_require_effective_authority"
        )

    effective = _effective_authority()
    monkeypatch.setattr(
        baseline,
        "_require_effective_authority",
        lambda: dict(effective),
    )
    monkeypatch.setattr(
        baseline,
        "_preflight_with_verified_authority",
        lambda authority: {"status": "preflight", "authority": dict(authority)},
    )
    monkeypatch.setattr(
        baseline,
        "_execute_one_shot_with_verified_authority",
        lambda authority: {"status": "executed", "authority": dict(authority)},
    )
    assert baseline.preflight(effective)["status"] == "preflight"
    assert baseline.execute_one_shot(effective)["status"] == "executed"
    forged = dict(effective)
    forged["p_patch_head"] = "9" * 40
    with pytest.raises(baseline.BaselineDevelopmentError, match="differs"):
        baseline.preflight(forged)
    with pytest.raises(baseline.BaselineDevelopmentError, match="differs"):
        baseline.execute_one_shot(forged)


def test_hardlink_publication_is_no_clobber_and_rollback_is_inode_owned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(baseline, "PROJECT_ROOT", tmp_path)
    final = tmp_path / "bundle.json"
    with pytest.raises(RuntimeError, match="injected"):
        with baseline.OutputTransaction() as transaction:
            transaction.publish_bytes(b"payload\n", final)
            assert final.read_bytes() == b"payload\n"
            replacement = tmp_path / "replacement"
            replacement.write_bytes(b"foreign\n")
            final.unlink()
            replacement.rename(final)
            raise RuntimeError("injected")
    assert final.read_bytes() == b"foreign\n"


def test_publication_refuses_existing_final_and_preserves_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(baseline, "PROJECT_ROOT", tmp_path)
    final = tmp_path / "bundle.json"
    final.write_bytes(b"foreign\n")
    with pytest.raises(baseline.BaselineDevelopmentError, match="overwrite final"):
        with baseline.OutputTransaction() as transaction:
            transaction.publish_bytes(b"payload\n", final)
    assert final.read_bytes() == b"foreign\n"
    assert not Path(final.as_posix() + ".tmp").exists()


def test_transaction_writes_parquet_and_joblib_through_owned_file_descriptors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(baseline, "PROJECT_ROOT", tmp_path)
    parquet_path = tmp_path / "data" / "scores.parquet"
    joblib_path = tmp_path / "models" / "pipeline.joblib"
    frame = pd.DataFrame({"value": [1.0, 2.0]})
    with baseline.OutputTransaction() as transaction:
        parquet = transaction.publish_arrow_table(pa.Table.from_pandas(frame), parquet_path)
        pipeline = transaction.publish_joblib({"seed": 1729}, joblib_path)
        assert transaction.file_record(parquet)["bytes"] > 0
        assert transaction.file_record(pipeline)["bytes"] > 0
    pd.testing.assert_frame_equal(pd.read_parquet(parquet_path), frame)
    assert baseline.joblib.load(joblib_path) == {"seed": 1729}
    assert not Path(parquet_path.as_posix() + ".tmp").exists()
    assert not Path(joblib_path.as_posix() + ".tmp").exists()


def test_publication_refuses_symlinked_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(baseline, "PROJECT_ROOT", tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    unsafe = tmp_path / "unsafe"
    unsafe.symlink_to(outside, target_is_directory=True)
    with pytest.raises(baseline.BaselineDevelopmentError, match="not a real directory"):
        with baseline.OutputTransaction() as transaction:
            transaction.publish_bytes(b"payload\n", unsafe / "bundle.json")
    assert not (outside / "bundle.json").exists()


def test_guard_cleanup_is_inode_owned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(baseline, "PROJECT_ROOT", tmp_path)
    guard_path = tmp_path / "tmp" / "baseline.guard"
    contract = {"outputs": {"publication": {"guard_path": guard_path.as_posix()}}}
    guard = baseline._acquire_guard(contract)
    guard_path.unlink()
    guard_path.write_bytes(b"foreign\n")
    with pytest.raises(baseline.BaselineDevelopmentError, match="guard cleanup"):
        baseline._release_guard(guard)
    assert guard_path.read_bytes() == b"foreign\n"


def test_guard_acquisition_failure_rolls_back_its_owned_inode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(baseline, "PROJECT_ROOT", tmp_path)
    guard_path = tmp_path / "tmp" / "baseline.guard"
    contract = {"outputs": {"publication": {"guard_path": guard_path.as_posix()}}}
    real_fsync = baseline.os.fsync
    calls = 0

    def injected_fsync(descriptor: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("injected guard fsync failure")
        real_fsync(descriptor)

    monkeypatch.setattr(baseline.os, "fsync", injected_fsync)
    with pytest.raises(OSError, match="injected guard fsync failure"):
        baseline._acquire_guard(contract)
    assert not guard_path.exists()


def test_preflight_namespace_rejects_future_dvc_pointer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = baseline.load_runtime_contract()
    monkeypatch.chdir(tmp_path)
    pointer = Path(contract["dvc"]["future_pointer_paths"][0])
    pointer.parent.mkdir(parents=True)
    pointer.write_text("outs: []\n", encoding="utf-8")
    with pytest.raises(baseline.BaselineDevelopmentError, match="namespace is not empty"):
        baseline._assert_absent_namespace(contract)


def test_file_record_rejects_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(baseline, "PROJECT_ROOT", tmp_path)
    target = tmp_path / "target.json"
    target.write_text("{}\n", encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(baseline.BaselineDevelopmentError, match="without following links"):
        baseline._file_record(link)
