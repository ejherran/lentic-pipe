from __future__ import annotations

import csv
import hashlib
import io
import inspect
import itertools
import json
import os
import stat
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

from src.experiments import calibrate_closure_final_models as runner
from src.experiments import (
    closure_final_calibration_raw_exclusion_evidence_patch as calibration,
)


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_OUTPUTS = (
    "reports/closure_v1/03_calibration/calibrator_specs.json",
    "reports/closure_v1/03_calibration/calibration_metrics.csv",
    "reports/closure_v1/03_calibration/alert_thresholds.csv",
    "reports/closure_v1/03_calibration/ordinal_cutpoints.csv",
    "reports/closure_v1/03_calibration/model_availability.csv",
    "reports/closure_v1/03_calibration/final_calibration_manifest.json",
)


def _relative_outputs(repo_root: Path) -> tuple[Path, ...]:
    return tuple(repo_root / path for path in EXPECTED_OUTPUTS)


def _runtime() -> dict[str, Any]:
    value = yaml.safe_load(
        (ROOT / "configs/closure_v1/final_calibration_runtime.yaml").read_text()
    )
    assert isinstance(value, dict)
    return value


def _model_availability() -> list[dict[str, Any]]:
    records = _runtime()["model_matrix"]["records"]
    return [dict(record) for record in records]


def _synthetic_predictions() -> pd.DataFrame:
    exact_counts = {
        1: {2019: 397, 2020: 261, 2021: 224},
        2: {2019: 371, 2020: 287, 2021: 224},
        3: {2019: 344, 2020: 314, 2021: 224},
    }
    rows: list[dict[str, Any]] = []
    for model_id in runner.CALIBRATABLE_MODELS:
        for model_seed in runner.MODEL_SEEDS[model_id]:
            for horizon in runner.HORIZONS:
                for year in (2019, 2020, 2021):
                    for index in range(exact_counts[horizon][year]):
                        target_month = cast(
                            pd.Period,
                            pd.Period(f"{year}-{index % 12 + 1:02d}", freq="M"),
                        )
                        origin_month = target_month - horizon
                        bloom_label = index % 2
                        ordinal_label = index % 4
                        rows.append(
                            {
                                "model_id": model_id,
                                "model_seed": model_seed,
                                "horizon_months": horizon,
                                "source_id": "wqp",
                                "site_id": f"site-{index:02d}",
                                "common_origin_id": (
                                    f"wqp:{horizon}:{year}:{index:04d}"
                                ),
                                "origin_year_month": str(origin_month),
                                "assignment_role": "development",
                                "time_role": (
                                    "model_selection"
                                    if year in {2019, 2020}
                                    else "calibration_threshold"
                                ),
                                "target_year_month": str(target_month),
                                "bloom_probability": (
                                    0.15 + 0.70 * bloom_label + (index % 3) * 0.01
                                ),
                                "bloom_label": bloom_label,
                                "ordinal_score": (
                                    (
                                        0.5
                                        if model_id == "B0"
                                        else (ordinal_label + 0.25) / 4.0
                                    )
                                    if model_id in runner.ORDINAL_MODELS
                                    else np.nan
                                ),
                                "ordinal_label": (
                                    ordinal_label
                                    if model_id in runner.ORDINAL_MODELS
                                    else np.nan
                                ),
                                "observed_risk": (
                                    float(index % 101) / 100.0
                                    if model_id in runner.UNCERTAINTY_MODELS
                                    else np.nan
                                ),
                                "predicted_risk": (
                                    max(0.0, float(index % 101) / 100.0 - 0.01)
                                    if model_id in runner.UNCERTAINTY_MODELS
                                    else np.nan
                                ),
                                "predicted_risk_sigma": (
                                    1.0
                                    if model_id in runner.UNCERTAINTY_MODELS
                                    else np.nan
                                ),
                            }
                        )
    frame = pd.DataFrame(rows)
    frame["ordinal_label"] = pd.array(frame["ordinal_label"], dtype="Int8")
    return frame


def _input_filter_evidence() -> list[dict[str, Any]]:
    evidence_digest = (
        "e56ce749c2787097b878fc7a44350797521d143cbb08322c9537cdd905c0dfd9"
    )
    rows_per_seed_horizon = 1380
    matched_per_seed_horizon = 882
    seed_counts = {"B0": 1, "B1": 5, "B2": 5, "M0": 1}
    counts = {
        model_id: (
            rows_per_seed_horizon * 3 * seed_count,
            matched_per_seed_horizon * 3 * seed_count,
            (rows_per_seed_horizon - matched_per_seed_horizon) * 3 * seed_count,
        )
        for model_id, seed_count in seed_counts.items()
    }
    paths = {
        "B0": "data/closure_v1/development/baselines/B0/raw_scores.parquet",
        "B1": "data/closure_v1/development/baselines/B1/raw_scores.parquet",
        "B2": "data/closure_v1/development/baselines/B2/raw_scores.parquet",
        "M0": "data/closure_v1/development/mifal/M0/raw_scores.parquet",
    }
    return [
        {
            "role": "target_predicate_scan_and_common_origin_projection",
            "scanner": "pyarrow_dataset_anchored_fd_predicate_pushdown",
            "predicate": (
                "source_id=wqp AND site_id IN development AND "
                "origin<=2021-12 AND 2019-01<=target<=2021-12"
            ),
            "materialized_row_count": 8743,
            "minimum_origin_year_month": "2018-10",
            "maximum_origin_year_month": "2021-11",
            "minimum_target_year_month": "2019-01",
            "maximum_target_year_month": "2021-12",
            "boundary_crossing_rows": 0,
            "holdout_rows_materialized": 0,
            "development_site_count": 121,
            "development_site_ids_sha256": (
                "42ece001484bdfa38ef8ac849e7b085ba14f244ee89f7a11474f377de721dea5"
            ),
            "projection": "exact_common_origin_key_inner_join",
            "projected_complete_target_row_count": 2646,
            "outside_common_origin_projection_row_count": 6097,
            "row_count_equation": (
                "materialized_row_count=projected_complete_target_row_count+"
                "outside_common_origin_projection_row_count"
            ),
        },
        *[
        {
            "model_id": model_id,
            "source_path": paths[model_id],
            "candidate_row_count": counts[model_id][0],
            "matched_target_row_count": counts[model_id][1],
            "excluded_incomplete_target_row_count": counts[model_id][2],
            "excluded_target_keys_sha256": evidence_digest,
        }
        for model_id in ("B0", "B1", "B2", "M0")
        ],
    ]


def _calibration_execution_policy() -> dict[str, Any]:
    return {
        "torch_cpu_execution_policy": {
            "device": "cpu",
            "torch_num_threads": 1,
            "torch_num_interop_threads": 1,
            "blas_thread_environment_control": "not_locked_by_e0_dl_v1",
            "bitwise_reproducibility_claim": (
                "forbidden_across_processes_or_blas_backends"
            ),
            "torch_num_threads_observed": 1,
            "torch_num_interop_threads_observed": 1,
        },
        "development_runtime_schema_version": "closure_development_runtime_v1",
        "development_runtime_audit_sha256": (
            calibration.EXPECTED_DEVELOPMENT_RUNTIME_AUDIT_SHA256
        ),
        "threadpool_limit": 1,
    }


def _rewrite_csv(
    payload: bytes,
    mutate: Any,
) -> bytes:
    reader = csv.reader(io.StringIO(payload.decode("utf-8"), newline=""))
    table = list(reader)
    mutate(table)
    destination = io.StringIO(newline="")
    writer = csv.writer(destination, lineterminator="\n")
    writer.writerows(table)
    return destination.getvalue().encode("utf-8")


def _synthetic_target_frames(
    predictions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    reference = predictions.loc[
        predictions["model_id"].eq("B0") & predictions["model_seed"].eq(1729)
    ].copy()
    trophic = np.asarray(runner.TROPHIC_LABELS, dtype=object)
    targets = reference.loc[:, list(runner.TARGET_JOIN_COLUMNS)].copy()
    targets["bloom_h"] = reference["bloom_label"].astype(bool).to_numpy()
    target_row = (
        reference["common_origin_id"]
        .str.rsplit(":", n=1)
        .str[-1]
        .astype("int64")
    )
    targets["target_risk_chla_h"] = (target_row % 101) / 100.0
    targets["target_trophic_state_h"] = trophic[
        reference["ordinal_label"].astype("int64").to_numpy()
    ]
    common = reference.loc[
        :,
        [
            "source_id",
            "site_id",
            "common_origin_id",
            "assignment_role",
            "time_role",
            "origin_year_month",
            "target_year_month",
            "horizon_months",
        ],
    ].copy()
    common["input_eligible"] = True
    common["complete_targets_evaluable"] = True
    return targets.reset_index(drop=True), common.reset_index(drop=True)


def _synthetic_raw_score_frames(
    predictions: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for model_id in ("B0", "B1", "B2", "M0"):
        source = predictions.loc[predictions["model_id"].eq(model_id)].copy()
        raw = pd.DataFrame(
            {
                "model_id": model_id,
                "source_id": source["source_id"],
                "site_id": source["site_id"],
                "common_origin_id": source["common_origin_id"],
                "assignment_role": source["assignment_role"],
                "time_role": source["time_role"],
                "origin_year_month": source["origin_year_month"],
                "target_year_month": source["target_year_month"],
                "horizon_months": source["horizon_months"],
                "technical_seed": source["model_seed"],
                "model_seed": source["model_seed"],
                "upstream_state_seed": source["model_seed"],
                "candidate": (
                    "hist_gradient_boosting_classifier"
                    if model_id == "B2"
                    else (
                        "mifal_ed_t2_v5_defaults" if model_id == "M0" else ""
                    )
                ),
                "selected_family": model_id == "B2",
                "availability_status": "success",
                "failure_reason": "",
                "raw_score": (
                    source["bloom_probability"]
                    if model_id == "M0"
                    else source["ordinal_score"]
                ),
                "predicted_bloom_probability": (
                    np.nan
                    if model_id == "M0"
                    else source["bloom_probability"]
                ),
            }
        ).reset_index(drop=True)
        if model_id == "B2":
            unselected = raw.copy()
            unselected["candidate"] = "logistic_sgd"
            unselected["selected_family"] = False
            raw = pd.concat([raw, unselected], ignore_index=True)
        extras: list[pd.DataFrame] = []
        extra_source = (
            raw.loc[raw["selected_family"].eq(True)]
            if model_id == "B2"
            else raw
        )
        for raw_key, group in extra_source.groupby(
            ["model_seed", "horizon_months"], sort=True
        ):
            model_seed, horizon = cast(tuple[int, int], raw_key)
            for time_role, extra_count, offset in (
                ("model_selection", 403, 0),
                ("calibration_threshold", 95, 403),
            ):
                role_group = group.loc[group["time_role"].eq(time_role)].reset_index(
                    drop=True
                )
                assert not role_group.empty
                extra = role_group.iloc[
                    np.arange(extra_count) % len(role_group)
                ].copy()
                indexes = range(offset, offset + extra_count)
                extra["site_id"] = [
                    f"extra-site-{horizon}-{index:03d}" for index in indexes
                ]
                extra["common_origin_id"] = [
                    f"extra:{horizon}:{index:03d}" for index in indexes
                ]
                assert set(extra["model_seed"]) == {model_seed}
                extras.append(extra)
        frames[model_id] = pd.concat([raw, *extras], ignore_index=True)
    return frames


def test_constants_close_model_matrix_roles_and_exact_six_outputs() -> None:
    assert runner.METHODS == ("identity", "platt_logistic", "isotonic_regression")
    assert runner.CALIBRATABLE_MODELS == ("B0", "B1", "B2", "M0", "A0", "A1")
    assert runner.ORDINAL_MODELS == ("B0", "B1", "B2")
    assert runner.UNCERTAINTY_MODELS == ("A0", "A1")
    assert runner.HORIZONS == (1, 2, 3)
    assert runner.REGISTERED_SEEDS == (1729, 20260612, 20260613, 20260614, 314159)
    assert tuple(path.relative_to(ROOT).as_posix() for path in runner.OUTPUT_PATHS) == EXPECTED_OUTPUTS
    assert runner.OUTPUT_PATHS[-1] == runner.MANIFEST_PATH
    producer_candidates = {
        "B0": ("",),
        "B1": ("",),
        "B2": ("logistic_sgd", "hist_gradient_boosting_classifier"),
        "M0": ("mifal_ed_t2_v5_defaults",),
    }
    assert calibration.RAW_SCORE_CANDIDATE_VALUES == producer_candidates
    for model_id, values in producer_candidates.items():
        calibration.validate_raw_score_candidate_semantics(model_id, values)

    baseline_manifest = json.loads(
        (ROOT / "reports/closure_v1/02_models/baselines/manifest.json").read_bytes()
    )
    baseline_contract = baseline_manifest["raw_prediction_contract"]
    candidate_column = next(
        column
        for column in baseline_contract["columns"]
        if column["name"] == "candidate"
    )
    assert candidate_column == {
        "name": "candidate",
        "dtype": "string",
        "nullable": False,
    }
    assert baseline_manifest["counts"] == {
        "common_origin_rows": 29_196,
        "intent_origins": 9_732,
        "B0_raw_rows": 29_196,
        "B1_raw_rows": 145_980,
        "B2_candidate_raw_rows": 291_960,
        "pipeline_records": 30,
        "preprocessor_records": 30,
    }
    assert tuple(baseline_contract["candidate_order"]) == producer_candidates["B2"]
    baseline_source = (ROOT / "src/experiments/fit_closure_baselines.py").read_text()
    assert baseline_source.count('frame["candidate"].eq("")') == 2
    assert 'set(frame["candidate"].astype(str)) != set(CANDIDATES)' in baseline_source

    mifal_manifest = json.loads(
        (ROOT / "reports/closure_v1/02_models/M0/manifest.json").read_bytes()
    )
    mifal_contract = mifal_manifest["raw_prediction_contract"]
    assert mifal_manifest["counts"]["raw_rows"] == 29_196
    assert (
        mifal_contract["candidate_policy"]
        == "constant_mifal_ed_t2_v5_defaults"
    )


def test_cli_is_one_shot_closed_and_translates_only_domain_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert runner.parse_args(["--check-only"]).check_only is True
    assert runner.parse_args(["--execute-one-shot"]).execute_one_shot is True
    for argv in ([], ["--check-only", "--execute-one-shot"], ["--execute-lock"]):
        with pytest.raises(SystemExit):
            runner.parse_args(argv)
    monkeypatch.setattr(runner, "check_only", lambda: {"status": "ready_to_calibrate"})
    assert runner.main(["--check-only"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ready_to_calibrate"

    def fail() -> dict[str, Any]:
        raise calibration.FinalCalibrationError("closed")

    monkeypatch.setattr(runner, "execute_one_shot", fail)
    assert runner.main(["--execute-one-shot"]) == 2
    assert capsys.readouterr().err.strip() == "closed"


def test_check_only_requires_effective_p_before_any_scientific_io(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert runner.calibration is calibration
    assert calibration.PATCH_GATE == "E0-MCALF"
    calls: list[tuple[bool, Path]] = []
    events: list[str] = []
    authority = {"gate": calibration.PATCH_GATE, "status": "effective"}

    def require(*, verify_remote: bool, repo_root: Path) -> dict[str, Any]:
        events.append("gate")
        calls.append((verify_remote, repo_root))
        return authority

    namespace = {
        "runner": "calibration",
        "r_lifecycle_state": "ready_for_calibration_bundle",
        "calibration_bundle_absent": True,
    }

    def require_namespace(*, runner: str, repo_root: Path) -> dict[str, Any]:
        assert runner == "calibration" and repo_root == tmp_path
        events.append("namespace")
        return namespace

    monkeypatch.setattr(
        calibration, "require_final_calibration_authority", require
    )
    monkeypatch.setattr(
        calibration,
        "require_final_calibration_run_namespace",
        require_namespace,
    )
    result = runner.check_only(repo_root=tmp_path)
    assert calls == [(True, tmp_path)]
    assert events == ["gate", "namespace"]
    assert result["authority"] is authority
    assert result["namespace"] is namespace
    assert result["output_count"] == 6
    for key in (
        "writes_performed",
        "calibration_run",
        "dvc_commands_run",
        "scientific_network_commands_run",
        "holdout_accessed",
        "post_2021_rows_accessed",
        "future_outcomes_accessed",
    ):
        assert result[key] is False
    assert list(tmp_path.iterdir()) == []
    monkeypatch.setattr(
        calibration,
        "require_final_calibration_authority",
        lambda **_: (_ for _ in ()).throw(calibration.FinalCalibrationError("gate")),
    )
    events.clear()
    with pytest.raises(calibration.FinalCalibrationError, match="gate"):
        runner.check_only(repo_root=tmp_path)
    assert events == []
    assert list(tmp_path.iterdir()) == []


def test_identity_calibrator_is_exact_and_rejects_malformed_vectors() -> None:
    scores = np.asarray([0.0, 0.25, 0.75, 1.0])
    labels = np.asarray([0, 0, 1, 1])
    spec = runner.fit_calibrator_spec("identity", scores, labels)
    assert spec == {"method": "identity", "parameters": {}, "fit_rows": 4}
    np.testing.assert_array_equal(runner.apply_calibrator_spec(spec, scores), scores)
    malformed: list[tuple[Any, Any]] = [
        ([], []),
        ([0.1], [0, 1]),
        ([float("nan")], [0]),
        ([-0.1], [0]),
        ([1.1], [1]),
        ([0.5], [2]),
        ([[0.5]], [1]),
    ]
    for bad_scores, bad_labels in malformed:
        with pytest.raises(calibration.FinalCalibrationError):
            runner.fit_calibrator_spec("identity", bad_scores, bad_labels)


def test_platt_calibrator_is_deterministic_bounded_and_needs_both_classes() -> None:
    scores = [0.05, 0.15, 0.30, 0.70, 0.85, 0.95]
    labels = [0, 0, 0, 1, 1, 1]
    first = runner.fit_calibrator_spec("platt_logistic", scores, labels)
    second = runner.fit_calibrator_spec("platt_logistic", scores, labels)
    assert first == second
    values = runner.apply_calibrator_spec(first, [0.0, 0.5, 1.0])
    assert np.isfinite(values).all()
    assert np.all((values >= 0.0) & (values <= 1.0))
    assert np.all(np.diff(values) > 0.0)
    with pytest.raises(calibration.FinalCalibrationError, match="both binary classes"):
        runner.fit_calibrator_spec("platt_logistic", [0.1, 0.2], [0, 0])


def test_isotonic_calibrator_is_monotone_clipped_and_spec_is_fail_closed() -> None:
    spec = runner.fit_calibrator_spec(
        "isotonic_regression",
        [0.05, 0.20, 0.40, 0.60, 0.80, 0.95],
        [0, 0, 1, 0, 1, 1],
    )
    values = runner.apply_calibrator_spec(spec, [0.0, 0.3, 0.7, 1.0])
    assert np.all(np.diff(values) >= 0.0)
    assert np.all((values >= 0.0) & (values <= 1.0))
    malformed = [
        {"method": "unknown", "parameters": {}},
        {"method": "identity", "parameters": []},
        {"method": "isotonic_regression", "parameters": {"x_thresholds": [0, 0], "y_thresholds": [0, 1]}},
        {"method": "isotonic_regression", "parameters": {"x_thresholds": [0, 1], "y_thresholds": [1, 0]}},
    ]
    for drift in malformed:
        with pytest.raises(calibration.FinalCalibrationError):
            runner.apply_calibrator_spec(drift, [0.5])


def test_method_selection_uses_brier_window_ece_then_simplicity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    codes = {"identity": 0.0, "platt_logistic": 1.0, "isotonic_regression": 2.0}
    briers = {0.0: 0.1000, 1.0: 0.1005, 2.0: 0.1020}
    eces = {0.0: 0.05, 1.0: 0.04, 2.0: 0.00}
    monkeypatch.setattr(
        runner,
        "fit_calibrator_spec",
        lambda method, *_: {"method": method, "parameters": {}},
    )
    monkeypatch.setattr(
        runner,
        "apply_calibrator_spec",
        lambda spec, _scores: np.asarray([codes[str(spec["method"])]]),
    )
    monkeypatch.setattr(runner, "brier_score", lambda _labels, values: briers[float(values[0])])
    monkeypatch.setattr(
        runner,
        "expected_calibration_error",
        lambda _labels, values: eces[float(values[0])],
    )
    selected, rows = runner.select_calibration_method([0], [0], [0], [0])
    assert selected == "platt_logistic"
    assert [row["method"] for row in rows] == list(runner.METHODS)

    eces[0.0] = eces[1.0]
    selected, _ = runner.select_calibration_method([0], [0], [0], [0])
    assert selected == "identity"


def test_method_selection_rejects_tolerance_and_type_drifts() -> None:
    args = ([0.1, 0.9], [0, 1], [0.2, 0.8], [0, 1])
    for tolerance in (-0.001, 0.0, 0.002, float("nan"), True, "0.001"):
        malformed_tolerance: Any = tolerance
        with pytest.raises(calibration.FinalCalibrationError):
            runner.select_calibration_method(
                *args, tolerance=malformed_tolerance
            )


def test_brier_and_ece_are_exact_and_reject_probability_drifts() -> None:
    labels = [0, 1, 1, 0]
    probabilities = [0.1, 0.8, 0.6, 0.2]
    assert runner.brier_score(labels, probabilities) == pytest.approx(0.0625)
    assert runner.expected_calibration_error(labels, probabilities) == pytest.approx(0.225)
    for bad in ([-0.1], [1.1], [float("nan")], [[0.5]]):
        malformed_probabilities: Any = bad
        with pytest.raises(calibration.FinalCalibrationError):
            runner.brier_score([0], malformed_probabilities)
        with pytest.raises(calibration.FinalCalibrationError):
            runner.expected_calibration_error([0], malformed_probabilities)
    for bins in (9, 11, True, 10.0):
        malformed_bins: Any = bins
        with pytest.raises(calibration.FinalCalibrationError):
            runner.expected_calibration_error(
                labels, probabilities, bins=malformed_bins
            )


def test_alert_threshold_matches_locked_f2_tie_break_and_rejects_drifts() -> None:
    probabilities = np.asarray([0.05, 0.25, 0.50, 0.75, 0.95])
    labels = np.asarray([0, 1, 0, 1, 1])
    observed = runner.select_alert_threshold(probabilities, labels)
    candidates = np.unique(np.concatenate((probabilities, [0.0, 0.5, 1.0])))
    reference: list[dict[str, float]] = []
    for threshold in candidates:
        predicted = probabilities >= threshold
        tp = int(np.logical_and(predicted, labels == 1).sum())
        fp = int(np.logical_and(predicted, labels == 0).sum())
        fn = int(np.logical_and(~predicted, labels == 1).sum())
        recall = tp / (tp + fn) if tp + fn else 0.0
        precision = tp / (tp + fp) if tp + fp else 0.0
        f2 = 5 * precision * recall / (4 * precision + recall) if 4 * precision + recall else 0.0
        reference.append({"threshold": float(threshold), "f2": f2, "recall": recall, "precision": precision})
    assert observed == max(reference, key=lambda row: (row["f2"], row["recall"], row["precision"], -row["threshold"]))
    for bad_probabilities, bad_labels, beta in (([-0.1], [0], 2.0), ([1.1], [1], 2.0), ([0.5], [2], 2.0), ([0.5], [1], 1.0), ([0.5], [1], True)):
        with pytest.raises(calibration.FinalCalibrationError):
            runner.select_alert_threshold(bad_probabilities, bad_labels, beta=beta)


def test_ordinal_cutpoints_are_monotone_reference_optimal_and_type_strict() -> None:
    scores = np.asarray([0.05, 0.15, 0.30, 0.45, 0.55, 0.70, 0.85, 0.95])
    labels = np.asarray([0, 0, 1, 1, 2, 2, 3, 3])
    observed = runner.select_ordinal_cutpoints(scores, labels)
    cutpoints = observed["cutpoints"]
    assert len(cutpoints) == 3
    assert cutpoints == sorted(cutpoints)
    assert observed["macro_f1"] == pytest.approx(1.0)
    assert observed["ordinal_mae"] == pytest.approx(0.0)
    for bad_scores, bad_labels in (([0.1, 0.2, 0.3], [0, 1, 2]), ([0.1, 0.2, 0.3, 0.4], [0.9, 1, 2, 3]), ([0.1, 0.2, 0.3, 0.4], [0, 1, 2, 4]), ([0.1, 0.2, 0.3, 0.4], [0, 1, 2])):
        malformed_scores: Any = bad_scores
        malformed_labels: Any = bad_labels
        with pytest.raises(calibration.FinalCalibrationError):
            runner.select_ordinal_cutpoints(malformed_scores, malformed_labels)

    def brute_force(
        values: list[float], targets: list[int]
    ) -> tuple[list[float], float, float]:
        score_array = np.asarray(values, dtype=np.float64)
        target_array = np.asarray(targets, dtype=np.int8)
        unique = np.unique(score_array)
        candidates = (unique[:-1] + unique[1:]) / 2.0
        evaluated: list[tuple[float, float, tuple[float, float, float]]] = []
        for cuts in itertools.combinations(candidates.tolist(), 3):
            predicted = np.searchsorted(
                np.asarray(cuts), score_array, side="right"
            ).astype(np.int8)
            macro_f1, ordinal_mae = runner._ordinal_metrics(
                target_array, predicted
            )
            evaluated.append((macro_f1, ordinal_mae, tuple(cuts)))
        best_f1 = max(row[0] for row in evaluated)
        f1_tied = [row for row in evaluated if abs(row[0] - best_f1) <= 1e-15]
        best_mae = min(row[1] for row in f1_tied)
        best = min(
            (row for row in f1_tied if abs(row[1] - best_mae) <= 1e-15),
            key=lambda row: row[2],
        )
        return list(best[2]), best[0], best[1]

    for repeated_scores, repeated_labels in (
        (
            [0.0, 0.0, 0.2, 0.2, 0.4, 0.4, 0.6, 0.6, 0.8, 0.8],
            [0, 1, 0, 1, 2, 1, 2, 3, 2, 3],
        ),
        (
            [0.0, 0.1, 0.1, 0.2, 0.3, 0.3, 0.4, 0.5, 0.5],
            [0, 0, 1, 2, 1, 3, 2, 3, 3],
        ),
        (
            [0.0, 0.0, 0.25, 0.25, 0.5, 0.5, 0.75, 0.75, 1.0, 1.0],
            [0, 2, 1, 3, 0, 2, 1, 3, 0, 2],
        ),
        (
            [1.0, 4 / 7, 2 / 7, 6 / 7, 5 / 7, 4 / 7, 0.0, 1 / 7, 4 / 7, 6 / 7, 3 / 7, 1.0, 4 / 7],
            [1, 1, 2, 3, 0, 0, 0, 3, 2, 3, 1, 1, 2],
        ),
    ):
        reference_cuts, reference_f1, reference_mae = brute_force(
            repeated_scores, repeated_labels
        )
        dynamic = runner.select_ordinal_cutpoints(
            repeated_scores, repeated_labels
        )
        assert dynamic["cutpoints"] == reference_cuts
        assert dynamic["macro_f1"] == pytest.approx(reference_f1)
        assert dynamic["ordinal_mae"] == pytest.approx(reference_mae)
    adversarial = runner.select_ordinal_cutpoints(
        [1.0, 4 / 7, 2 / 7, 6 / 7, 5 / 7, 4 / 7, 0.0, 1 / 7, 4 / 7, 6 / 7, 3 / 7, 1.0, 4 / 7],
        [1, 1, 2, 3, 0, 0, 0, 3, 2, 3, 1, 1, 2],
    )
    assert adversarial["cutpoints"] == pytest.approx([1 / 14, 1 / 2, 11 / 14])
    assert adversarial["ordinal_mae"] == pytest.approx(12 / 13)

    large_scores = np.linspace(0.0, 1.0, 4096)
    large_labels = np.repeat(np.arange(4), 1024)
    scalable = runner.select_ordinal_cutpoints(large_scores, large_labels)
    expected_cuts = [
        float((large_scores[index] + large_scores[index + 1]) / 2.0)
        for index in (1023, 2047, 3071)
    ]
    assert scalable == {
        "cutpoints": expected_cuts,
        "macro_f1": 1.0,
        "ordinal_mae": 0.0,
    }


def test_split_conformal_uses_locked_one_based_order_statistic_without_pooling() -> None:
    observed = np.arange(1.0, 31.0)
    predicted = np.zeros(30)
    sigma = np.ones(30)
    rows = runner.split_conformal_q_c(observed, predicted, sigma)
    assert [(row["coverage_level"], row["order_statistic_rank"], row["q_c"]) for row in rows] == [
        (0.80, 25, 25.0),
        (0.90, 28, 28.0),
        (0.95, 30, 30.0),
    ]
    unavailable = runner.split_conformal_q_c(observed[:-1], predicted[:-1], sigma[:-1])
    assert [row["status"] for row in unavailable] == [
        "not_available_insufficient_finite_rows"
    ] * 3
    assert all(row["q_c"] is None and row["finite_rows"] == 29 for row in unavailable)


def test_split_conformal_rejects_group_policy_and_numeric_type_drifts() -> None:
    observed = np.arange(30.0)
    predicted = np.zeros(30)
    sigma = np.ones(30)
    cases: tuple[dict[str, Any], ...] = (
        {"levels": (0.90, 0.80, 0.95)},
        {"levels": (0.80, 0.90, 0.90)},
        {"levels": (0.80, 0.90)},
        {"minimum_rows": 29},
        {"minimum_rows": True},
        {"scale_floor": 0.0},
        {"scale_floor": -0.1},
        {"scale_floor": 1e-5},
    )
    for kwargs in cases:
        with pytest.raises(calibration.FinalCalibrationError):
            runner.split_conformal_q_c(observed, predicted, sigma, **kwargs)
    with pytest.raises(calibration.FinalCalibrationError):
        runner.split_conformal_q_c(observed, predicted, np.zeros(30))


def test_ordered_publisher_requires_unique_manifest_last_and_canonical_outputs(
    tmp_path: Path,
) -> None:
    outputs = _relative_outputs(tmp_path)
    payloads = [(path, f"payload-{index}\n".encode()) for index, path in enumerate(outputs)]
    records = runner.publish_ordered_bundle(
        payloads,
        manifest_path=outputs[-1],
        guard_path=tmp_path / "tmp/guard",
        repo_root=tmp_path,
    )
    assert [record["path"] for record in records] == list(EXPECTED_OUTPUTS)
    for (path, payload), record in zip(payloads, records, strict=True):
        observed = path.stat()
        assert path.read_bytes() == payload
        assert stat.S_IMODE(observed.st_mode) == 0o644
        assert observed.st_nlink == 1
        assert record["sha256"] == hashlib.sha256(payload).hexdigest()
    assert not (tmp_path / "tmp/guard").exists()
    for malformed in (
        payloads[:-1],
        [payloads[0], payloads[0], payloads[-1]],
        [payloads[-1], payloads[0]],
    ):
        with pytest.raises(calibration.FinalCalibrationError):
            runner.publish_ordered_bundle(
                malformed,
                manifest_path=outputs[-1],
                guard_path=tmp_path / "tmp/other.guard",
                repo_root=tmp_path,
            )


def test_ordered_publisher_rolls_back_all_owned_and_never_clobbers_foreign(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    outputs = tuple(tmp_path / f"bundle/{name}" for name in ("a.json", "b.csv", "manifest.json"))
    payloads = [(path, path.name.encode()) for path in outputs]
    real_publish = runner._publish_one
    calls = 0

    def fail_fourth(path: Path, payload: bytes, *, repo_root: Path) -> runner.OwnedOutput:
        nonlocal calls
        calls += 1
        if calls == 4:
            raise calibration.FinalCalibrationError("injected")
        return real_publish(path, payload, repo_root=repo_root)

    monkeypatch.setattr(runner, "_publish_one", fail_fourth)
    with pytest.raises(calibration.FinalCalibrationError, match="injected"):
        runner.publish_ordered_bundle(
            payloads,
            manifest_path=outputs[-1],
            guard_path=tmp_path / "tmp/guard",
            repo_root=tmp_path,
        )
    assert all(not path.exists() for path in outputs)
    assert not (tmp_path / "tmp/guard").exists()
    assert not (tmp_path / "tmp").exists()
    assert not outputs[0].parent.exists()

    real_write_all = runner._write_all

    def fail_output_write(descriptor: int, payload: bytes, *, context: str) -> None:
        if "write-failure" in context:
            raise calibration.FinalCalibrationError("injected write")
        real_write_all(descriptor, payload, context=context)

    write_outputs = tuple(
        tmp_path / f"write-failure/{name}"
        for name in ("a.json", "b.csv", "manifest.json")
    )
    monkeypatch.setattr(runner, "_write_all", fail_output_write)
    with pytest.raises(calibration.FinalCalibrationError, match="injected write"):
        runner.publish_ordered_bundle(
            [(path, path.name.encode()) for path in write_outputs],
            manifest_path=write_outputs[-1],
            guard_path=tmp_path / "tmp/write.guard",
            repo_root=tmp_path,
        )
    assert not write_outputs[0].parent.exists()
    assert not (tmp_path / "tmp").exists()

    monkeypatch.setattr(runner, "_write_all", real_write_all)
    real_link = runner.os.link

    def fail_output_link(
        src: str, dst: str, *args: Any, **kwargs: Any
    ) -> None:
        if dst == "a.json":
            raise OSError("injected link")
        real_link(src, dst, *args, **kwargs)

    link_outputs = tuple(
        tmp_path / f"link-failure/{name}"
        for name in ("a.json", "b.csv", "manifest.json")
    )
    monkeypatch.setattr(runner.os, "link", fail_output_link)
    with pytest.raises(OSError, match="injected link"):
        runner.publish_ordered_bundle(
            [(path, path.name.encode()) for path in link_outputs],
            manifest_path=link_outputs[-1],
            guard_path=tmp_path / "tmp/link.guard",
            repo_root=tmp_path,
        )
    assert not link_outputs[0].parent.exists()
    assert not (tmp_path / "tmp").exists()

    monkeypatch.setattr(runner.os, "link", real_link)
    real_fsync = runner.os.fsync

    def fail_output_fsync(descriptor: int) -> None:
        try:
            target = os.readlink(f"/proc/self/fd/{descriptor}")
        except OSError:
            target = ""
        if "fsync-failure" in target:
            raise OSError("injected fsync")
        real_fsync(descriptor)

    fsync_outputs = tuple(
        tmp_path / f"fsync-failure/{name}"
        for name in ("a.json", "b.csv", "manifest.json")
    )
    monkeypatch.setattr(runner.os, "fsync", fail_output_fsync)
    with pytest.raises(OSError, match="injected fsync"):
        runner.publish_ordered_bundle(
            [(path, path.name.encode()) for path in fsync_outputs],
            manifest_path=fsync_outputs[-1],
            guard_path=tmp_path / "tmp/fsync.guard",
            repo_root=tmp_path,
        )
    assert not fsync_outputs[0].parent.exists()
    assert not (tmp_path / "tmp").exists()

    monkeypatch.setattr(runner, "_publish_one", real_publish)
    monkeypatch.setattr(runner.os, "fsync", real_fsync)
    outputs[0].parent.mkdir(parents=True, exist_ok=True)
    outputs[0].write_bytes(b"foreign")
    with pytest.raises(calibration.FinalCalibrationError, match="already exists"):
        runner.publish_ordered_bundle(
            payloads,
            manifest_path=outputs[-1],
            guard_path=tmp_path / "tmp/second.guard",
            repo_root=tmp_path,
        )
    assert outputs[0].read_bytes() == b"foreign"
    assert all(not path.exists() for path in outputs[1:])
    assert outputs[0].parent.is_dir()
    assert not (tmp_path / "tmp").exists()

    race_outputs = tuple(
        tmp_path / f"race/{name}" for name in ("a.json", "b.csv", "manifest.json")
    )
    race_payloads = [(path, (path.name + "\n").encode()) for path in race_outputs]
    race_guard = tmp_path / "tmp/race.guard"
    real_unlink = runner._unlink_owned
    injected = False

    def mutate_during_guard_release(
        path: Path, owned: runner.OwnedOutput, *, repo_root: Path
    ) -> None:
        nonlocal injected
        if path == race_guard and not injected:
            injected = True
            race_outputs[0].write_bytes(b"X" * len(race_payloads[0][1]))
        real_unlink(path, owned, repo_root=repo_root)

    monkeypatch.setattr(runner, "_unlink_owned", mutate_during_guard_release)
    with pytest.raises(calibration.FinalCalibrationError, match="drift|commit|rollback"):
        runner.publish_ordered_bundle(
            race_payloads,
            manifest_path=race_outputs[-1],
            guard_path=race_guard,
            repo_root=tmp_path,
        )
    assert injected is True
    assert all(not path.exists() for path in race_outputs)
    assert not race_guard.exists()
    assert not race_outputs[0].parent.exists()
    assert not (tmp_path / "tmp").exists()


def test_runner_build_and_execute_are_closed_functional_and_revalidate_before_io(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = inspect.getsource(runner)
    assert (
        "closure_final_calibration_raw_exclusion_evidence_patch as calibration"
        in source
    )
    evidence_parser_source = inspect.getsource(runner._validate_input_filter_evidence)
    assert "calibration." not in evidence_parser_source
    assert "target_filter_evidence_patch" not in evidence_parser_source
    execute_source = inspect.getsource(runner.execute_one_shot)
    require_offset = execute_source.index("require_final_calibration_authority")
    scientific_offsets = [
        execute_source.find(token)
        for token in ("read_parquet", "dataset(", "build_final_calibration_bundle(")
        if execute_source.find(token) >= 0
    ]
    assert scientific_offsets
    assert all(require_offset < offset for offset in scientific_offsets)
    for name in (
        "fit_calibrator_spec",
        "apply_calibrator_spec",
        "select_calibration_method",
        "select_alert_threshold",
        "select_ordinal_cutpoints",
        "split_conformal_q_c",
        "build_final_calibration_bundle",
        "publish_ordered_bundle",
    ):
        assert callable(getattr(runner, name))
    assert "dvc add" not in source
    assert "dvc push" not in source

    predictions = _synthetic_predictions()
    assert len(predictions) == 66 * 882
    target_counts = (
        predictions.assign(_year=predictions["target_year_month"].str[:4])
        .groupby(["model_id", "model_seed", "horizon_months", "_year"])
        .size()
    )
    assert len(target_counts) == 66 * 3
    assert set(target_counts) == {224, 261, 287, 314, 344, 371, 397}
    assert int(np.asarray(target_counts, dtype=np.int64).sum()) == len(predictions)
    target_frame, common_frame = _synthetic_target_frames(predictions)
    real_read_parquet = runner._read_parquet_frame
    real_stable_record = runner.stable_file_record

    common_path = tmp_path / "data/closure_v1/common_origin_manifest.parquet"
    target_path = tmp_path / "data/targets/monthly_targets_model_v0.parquet"
    common_path.parent.mkdir(parents=True)
    target_path.parent.mkdir(parents=True)
    pq.write_table(pa.Table.from_pandas(common_frame, preserve_index=False), common_path)
    poison_2022 = target_frame.head(12).copy()
    poison_2022["origin_year_month"] = "2022-01"
    poison_2022["target_year_month"] = "2022-02"
    outside_common = target_frame.head(1).copy()
    outside_common["origin_year_month"] = "2019-01"
    outside_common["target_year_month"] = "2019-02"
    outside_common["horizon_months"] = 1
    outside_key = tuple(
        outside_common.loc[0, list(runner.TARGET_JOIN_COLUMNS)].tolist()
    )
    assert outside_key not in set(
        common_frame.loc[:, list(runner.TARGET_JOIN_COLUMNS)].itertuples(
            index=False,
            name=None,
        )
    )
    physical_targets = pd.concat(
        [target_frame, outside_common, poison_2022], ignore_index=True
    )

    def write_targets(frame: pd.DataFrame) -> None:
        pq.write_table(
            pa.Table.from_pandas(frame, preserve_index=False),
            target_path,
        )

    write_targets(physical_targets)
    for relative in (
        "data/closure_v1/common_origin_manifest.parquet.dvc",
        "reports/closure_v1/01_surface/common_origin_manifest.json",
        "data/targets.dvc",
        "data/targets/target_manifest_v0.json",
    ):
        authority_path = tmp_path / relative
        authority_path.parent.mkdir(parents=True, exist_ok=True)
        authority_path.write_bytes((relative + "\n").encode())

    real_dataset = runner.ds.dataset
    scanner_calls: list[dict[str, Any]] = []
    models_pointer = tmp_path / "models.dvc"
    models_pointer.write_text(
        "outs:\n"
        f"- md5: {'0' * 32}.dir\n"
        "  size: 1\n"
        "  nfiles: 1\n"
        "  hash: md5\n"
        "  path: models\n",
        encoding="utf-8",
    )
    models_pointer.chmod(0o644)
    authorized_pointers = (Path("models.dvc"),)
    assert runner._authorized_scientific_dvc_pointers(
        {
            "scientific_input_inventory": {
                "authority_records": [{"path": "models.dvc"}],
                "payload_bindings": [{"path": "models/probe.bin"}],
            }
        }
    ) == authorized_pointers

    class DatasetProbe:
        def __init__(self, dataset: Any, source: str) -> None:
            self._dataset = dataset
            self.schema = dataset.schema
            self._source = source

        def scanner(self, *, columns: Any, filter: Any) -> Any:
            scanner_calls.append(
                {
                    "source": self._source,
                    "columns": tuple(columns),
                    "filter": str(filter),
                }
            )
            return self._dataset.scanner(columns=columns, filter=filter)

    def dataset_probe(source: str, *, format: str) -> DatasetProbe:
        assert source.startswith("/proc/self/fd/")
        assert format == "parquet"
        return DatasetProbe(real_dataset(source, format=format), source)

    monkeypatch.setattr(runner.ds, "dataset", dataset_probe)

    def synthetic_record(path: Path) -> dict[str, Any]:
        relative = path.relative_to(tmp_path).as_posix()
        return {
            "path": relative,
            "bytes": 1,
            "sha256": "0" * 64,
            "mode": "0644",
            "nlink": 1,
            "device": 1,
            "inode": abs(hash(relative)),
            "mtime_ns": 1,
            "ctime_ns": 1,
        }

    projected, target_records, target_snapshot, target_scan = (
        runner._target_projection(
            authorized_dvc_pointers=authorized_pointers,
            repo_root=tmp_path,
        )
    )
    target_universe = projected.loc[
        :,
        [
            *runner.TARGET_JOIN_COLUMNS,
            "bloom_h",
            "target_risk_chla_h",
            "ordinal_label",
        ],
    ].copy()
    assert len(projected) == 2646
    assert projected["origin_year_month"].max() <= "2021-12"
    assert projected["target_year_month"].max() <= "2021-12"
    assert target_scan["role"] == (
        "target_predicate_scan_and_common_origin_projection"
    )
    assert target_scan["materialized_row_count"] == 2647
    assert target_scan["projection"] == "exact_common_origin_key_inner_join"
    assert target_scan["projected_complete_target_row_count"] == 2646
    assert target_scan["outside_common_origin_projection_row_count"] == 1
    assert target_scan["row_count_equation"] == (
        "materialized_row_count=projected_complete_target_row_count+"
        "outside_common_origin_projection_row_count"
    )
    assert len(target_scan) == 16
    assert target_scan["materialized_row_count"] == (
        target_scan["projected_complete_target_row_count"]
        + target_scan["outside_common_origin_projection_row_count"]
    )
    assert target_scan["boundary_crossing_rows"] == 0
    assert target_scan["maximum_target_year_month"] <= "2021-12"
    assert len(target_records) == len(target_snapshot) == 6
    assert len({record["path"] for record in target_records}) == 6
    assert scanner_calls
    assert scanner_calls[-1]["source"].startswith("/proc/self/fd/")
    assert "target_year_month" in scanner_calls[-1]["filter"]
    assert "2021-12" in scanner_calls[-1]["filter"]
    for column, poison in (
        ("bloom_h", 0.9),
        ("bloom_h", 1),
        ("bloom_h", "1"),
        ("horizon_months", 1.5),
        ("horizon_months", True),
        ("target_risk_chla_h", True),
        ("target_risk_chla_h", 1.1),
        ("target_risk_chla_h", float("inf")),
        ("target_trophic_state_h", "unknown"),
    ):
        poisoned = physical_targets.copy()
        if column == "bloom_h":
            if type(poison) is str:
                poisoned[column] = poisoned[column].astype(str)
            elif type(poison) is int:
                poisoned[column] = poisoned[column].astype("int64")
            else:
                poisoned[column] = poisoned[column].astype("float64")
        elif column == "horizon_months":
            poisoned[column] = (
                poisoned[column].astype(bool)
                if type(poison) is bool
                else poisoned[column].astype("float64")
            )
        elif column == "target_risk_chla_h" and type(poison) is bool:
            poisoned[column] = poisoned[column].astype(bool)
        poisoned.loc[0, column] = poison
        write_targets(poisoned)
        with pytest.raises(calibration.FinalCalibrationError):
            runner._target_projection(
                authorized_dvc_pointers=authorized_pointers,
                repo_root=tmp_path,
            )
    write_targets(physical_targets)
    monkeypatch.setattr(runner.ds, "dataset", real_dataset)
    monkeypatch.setattr(runner, "_read_parquet_frame", real_read_parquet)
    monkeypatch.setattr(runner, "stable_file_record", real_stable_record)
    raw_frames = _synthetic_raw_score_frames(predictions)
    for model_id, raw_frame in raw_frames.items():
        producer_rows = (
            raw_frame.loc[raw_frame["selected_family"].eq(True)]
            if model_id == "B2"
            else raw_frame
        )
        producer_groups = producer_rows.groupby(
            ["model_seed", "horizon_months"], sort=True
        ).size()
        assert producer_groups.eq(1380).all()
        assert len(producer_groups) == 3 * len(runner.MODEL_SEEDS[model_id])
    raw_box: dict[str, dict[str, pd.DataFrame]] = {"value": raw_frames}

    def read_raw(
        path: Path,
        *,
        columns: Any,
        authorized_dvc_pointers: Any,
        repo_root: Path,
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        assert repo_root == tmp_path
        assert authorized_dvc_pointers == authorized_pointers
        model_id = next(
            model for model in ("B0", "B1", "B2", "M0") if f"/{model}/" in path.as_posix()
        )
        return (
            raw_box["value"][model_id].loc[:, list(columns)].copy(),
            synthetic_record(path),
        )

    monkeypatch.setattr(runner, "_read_parquet_frame", read_raw)
    monkeypatch.setattr(
        runner,
        "stable_file_record",
        lambda path, *, repo_root: synthetic_record(path),
    )
    baseline, _, _, exclusion = runner._baseline_predictions(
        projected,
        authorized_dvc_pointers=authorized_pointers,
        repo_root=tmp_path,
    )
    assert len(baseline) == 31752
    assert baseline.groupby(
        ["model_id", "model_seed", "horizon_months"]
    ).size().eq(882).all()
    m0 = baseline[baseline["model_id"].eq("M0")]
    assert len(m0) == 2646
    assert m0["bloom_probability"].notna().all()
    exclusion_by_model = {record["model_id"]: record for record in exclusion}
    exclusion_digests: set[str] = set()
    for model_id, candidate, matched, excluded in (
        ("B0", 4140, 2646, 1494),
        ("B1", 20700, 13230, 7470),
        ("B2", 20700, 13230, 7470),
        ("M0", 4140, 2646, 1494),
    ):
        record = exclusion_by_model[model_id]
        assert record["candidate_row_count"] == candidate == matched + excluded
        assert record["matched_target_row_count"] == matched
        assert record["excluded_incomplete_target_row_count"] == excluded
        assert len(record["excluded_target_keys_sha256"]) == 64
        exclusion_digests.add(record["excluded_target_keys_sha256"])
    assert len(exclusion_digests) == 1
    pristine_m0 = raw_frames["M0"]
    for poison in (float("nan"), float("inf"), -0.1, 1.1, True, "0.5"):
        poisoned_m0 = pristine_m0.copy()
        if type(poison) in {bool, str}:
            poisoned_m0["raw_score"] = poisoned_m0["raw_score"].astype(object)
        poisoned_m0.loc[0, "raw_score"] = poison
        raw_box["value"] = {**raw_frames, "M0": poisoned_m0}
        try:
            runner._baseline_predictions(
                projected,
                authorized_dvc_pointers=authorized_pointers,
                repo_root=tmp_path,
            )
        except calibration.FinalCalibrationError:
            pass
        else:
            pytest.fail(f"M0 raw-score drift was accepted: {poison!r}")
    monkeypatch.setattr(runner, "_read_parquet_frame", real_read_parquet)
    monkeypatch.setattr(runner, "stable_file_record", real_stable_record)

    # Models/checkpoints are the one scientific-reader class that must accept
    # the immutable DVC representation (0444, exactly two links).  It must not
    # broaden that exception to read-only singletons, writable hardlinks, or a
    # third alias.
    physical_artifact = tmp_path / "models/torch_identity_probe.pt"
    physical_artifact.parent.mkdir(parents=True)
    torch_payload = b"synthetic torch payload\n"
    physical_artifact.write_bytes(torch_payload)
    torch_md5 = hashlib.md5(torch_payload, usedforsecurity=False).hexdigest()
    cache_artifact = (
        tmp_path / ".dvc/cache/files/md5" / torch_md5[:2] / torch_md5[2:]
    )
    cache_artifact.parent.mkdir(parents=True)
    os.link(physical_artifact, cache_artifact)
    physical_artifact.chmod(0o444)
    decode_torch = SimpleNamespace(
        load=lambda stream, **_: {"decoded": stream.read()}
    )
    monkeypatch.setattr(
        runner.anfis_training,
        "_require_torch",
        lambda: decode_torch,
    )
    decoded, _, dvc_snapshot = runner._torch_input(
        physical_artifact,
        role="a0_model_seed_1729",
        authorized_dvc_pointers=authorized_pointers,
        repo_root=tmp_path,
    )
    assert decoded == {"decoded": b"synthetic torch payload\n"}
    assert (dvc_snapshot["mode"], dvc_snapshot["nlink"]) == ("0444", 2)
    runner._revalidate_final_calibration_input_snapshot(
        [dvc_snapshot],
        authorized_dvc_pointers=authorized_pointers,
        repo_root=tmp_path,
    )

    # Parquet consumers use the same strict P-derived topology instead of a
    # path-only decoder.  Exercise the physical reader and its later snapshot
    # revalidation independently of the torch adapter.
    parquet_artifact = tmp_path / "models/parquet_identity_probe.parquet"
    pq.write_table(
        pa.table({"value": pa.array([1, 2], type=pa.int64())}),
        parquet_artifact,
    )
    parquet_payload = parquet_artifact.read_bytes()
    parquet_md5 = hashlib.md5(parquet_payload, usedforsecurity=False).hexdigest()
    parquet_cache = (
        tmp_path / ".dvc/cache/files/md5" / parquet_md5[:2] / parquet_md5[2:]
    )
    parquet_cache.parent.mkdir(parents=True, exist_ok=True)
    os.link(parquet_artifact, parquet_cache)
    parquet_artifact.chmod(0o444)
    parquet_frame, parquet_snapshot = runner._read_parquet_frame(
        parquet_artifact,
        columns=("value",),
        authorized_dvc_pointers=authorized_pointers,
        repo_root=tmp_path,
    )
    assert parquet_frame["value"].tolist() == [1, 2]
    assert (parquet_snapshot["mode"], parquet_snapshot["nlink"]) == ("0444", 2)
    runner._revalidate_final_calibration_input_snapshot(
        [parquet_snapshot],
        authorized_dvc_pointers=authorized_pointers,
        repo_root=tmp_path,
    )
    parquet_third = tmp_path / "models/parquet_identity_probe.third"
    os.link(parquet_artifact, parquet_third)
    with pytest.raises(calibration.FinalCalibrationError):
        runner._read_parquet_frame(
            parquet_artifact,
            columns=("value",),
            authorized_dvc_pointers=authorized_pointers,
            repo_root=tmp_path,
        )
    with pytest.raises(calibration.FinalCalibrationError):
        runner._revalidate_final_calibration_input_snapshot(
            [parquet_snapshot],
            authorized_dvc_pointers=authorized_pointers,
            repo_root=tmp_path,
        )
    parquet_third.unlink()
    parquet_artifact.chmod(0o644)
    with pytest.raises(calibration.FinalCalibrationError):
        runner._read_parquet_frame(
            parquet_artifact,
            columns=("value",),
            authorized_dvc_pointers=authorized_pointers,
            repo_root=tmp_path,
        )
    parquet_artifact.chmod(0o444)
    parquet_cache.unlink()
    with pytest.raises(calibration.FinalCalibrationError):
        runner._read_parquet_frame(
            parquet_artifact,
            columns=("value",),
            authorized_dvc_pointers=authorized_pointers,
            repo_root=tmp_path,
        )

    third_alias = tmp_path / "models/torch_identity_probe.third"
    os.link(physical_artifact, third_alias)
    with pytest.raises(calibration.FinalCalibrationError):
        runner._torch_input(
            physical_artifact,
            role="a0_model_seed_1729",
            authorized_dvc_pointers=authorized_pointers,
            repo_root=tmp_path,
        )
    with pytest.raises(calibration.FinalCalibrationError):
        runner._revalidate_final_calibration_input_snapshot(
            [dvc_snapshot],
            authorized_dvc_pointers=authorized_pointers,
            repo_root=tmp_path,
        )
    third_alias.unlink()
    physical_artifact.chmod(0o644)
    with pytest.raises(calibration.FinalCalibrationError):
        runner._torch_input(
            physical_artifact,
            role="a0_model_seed_1729",
            authorized_dvc_pointers=authorized_pointers,
            repo_root=tmp_path,
        )
    physical_artifact.chmod(0o444)
    cache_artifact.unlink()
    with pytest.raises(calibration.FinalCalibrationError):
        runner._torch_input(
            physical_artifact,
            role="a0_model_seed_1729",
            authorized_dvc_pointers=authorized_pointers,
            repo_root=tmp_path,
        )

    # A0/A1 2021 rows must be new inference from the published
    # model+checkpoint+preprocessor+sequence chain. Selection predictions and
    # adaptive state are never accepted as substitutes.
    inference_inputs: list[tuple[str, str]] = []
    sequence_calls: list[tuple[str, int]] = []
    identity_drift = {"enabled": False}

    def portable(path: Path, role: str) -> tuple[dict[str, Any], dict[str, Any]]:
        record = synthetic_record(path)
        snapshot = {"role": role, **record}
        return (
            {
                "role": role,
                "path": record["path"],
                "bytes": record["bytes"],
                "sha256": record["sha256"],
            },
            snapshot,
        )

    def sequence_input(
        *,
        model_id: str,
        base_seed: int,
        authorized_dvc_pointers: Any,
        repo_root: Path,
    ) -> tuple[pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]]]:
        assert repo_root == tmp_path
        assert authorized_dvc_pointers == authorized_pointers
        sequence_calls.append((model_id, base_seed))
        path = tmp_path / f"data/sequences/{model_id}/{base_seed}.parquet"
        one_portable, one_snapshot = portable(path, f"{model_id.lower()}_sequence")
        return pd.DataFrame({"slot": [base_seed]}), [one_portable], [one_snapshot]

    def torch_input(
        path: Path,
        *,
        role: str,
        authorized_dvc_pointers: Any,
        repo_root: Path,
    ) -> tuple[Mapping[str, Any], dict[str, Any], dict[str, Any]]:
        assert repo_root == tmp_path
        assert authorized_dvc_pointers == authorized_pointers
        inference_inputs.append((role, path.relative_to(tmp_path).as_posix()))
        model_id = "A0" if role.startswith("a0_") else "A1"
        base_seed = int(role.rsplit("_", 1)[1])
        artifact_role = (
            "raw_best_checkpoint" if "_checkpoint_" in role else "final_restored_model"
        )
        if identity_drift["enabled"] and len(inference_inputs) == 1:
            artifact_role = "adaptive_state_substitute"
        payload: Mapping[str, Any] = {
            "model_version": runner.anfis_training.MODEL_VERSION,
            "experiment_id": "closure_v1",
            "surface_id": runner.anfis_training.SURFACE_ID,
            "gate": "E0-MT",
            "model_id": model_id,
            "base_seed": base_seed,
            "device": runner.anfis_training.LOCKED_DEVICE,
            "config": runner.anfis_training._model_config(model_id),
            "artifact_role": artifact_role,
            "model_state_dict": {"weight": object()},
            "bloom_training_priors": [0.2, 0.3, 0.4],
            "risk_training_priors": [0.2, 0.3, 0.4],
        }
        one_portable, one_snapshot = portable(path, role)
        return payload, one_portable, one_snapshot

    def json_input(
        path: Path, *, role: str, repo_root: Path
    ) -> tuple[Mapping[str, Any], dict[str, Any], dict[str, Any]]:
        assert repo_root == tmp_path
        inference_inputs.append((role, path.relative_to(tmp_path).as_posix()))
        one_portable, one_snapshot = portable(path, role)
        if "_manifest_seed_" not in role:
            return {}, one_portable, one_snapshot
        model_id = role.split("_", 1)[0].upper()
        base_seed = int(role.rsplit("_", 1)[1])
        paths = runner.anfis_training.slot_paths(
            model_id, base_seed, repo_root=tmp_path
        )
        output_records = []
        for output_role in (
            "model",
            "checkpoint",
            "preprocessor",
            "training_curve",
            "selection_predictions",
            "selection_metrics",
            "report",
        ):
            record = synthetic_record(getattr(paths, output_role))
            output_records.append(
                {
                    "role": output_role,
                    "path": record["path"],
                    "bytes": record["bytes"],
                    "sha256": record["sha256"],
                }
            )
        script = {
            "role": "trainer",
            "path": "src/experiments/train_closure_anfis_ablation.py",
            "bytes": 1,
            "sha256": "0" * 64,
        }
        manifest = {
            "manifest_version": "closure_anfis_ablation_model_manifest_v1",
            "status": "completed",
            "slot_status": "available",
            "fit_status": "passed",
            "experiment_id": "closure_v1",
            "surface_id": runner.anfis_training.SURFACE_ID,
            "model_id": model_id,
            "base_seed": base_seed,
            "device": runner.anfis_training.LOCKED_DEVICE,
            "future_outcomes_accessed": False,
            "calibration_authorized": False,
            "calibration_target_accessed": False,
            "evaluation_authorized": False,
            "e0_m_authorized": False,
            "e0_u_authorized": False,
            "dvc_command_executed": False,
            "completion_marker_written_last": True,
            "authority": {
                "gate": (
                    "E0-MU"
                    if model_id == "A0" and base_seed == 1729
                    else "E0-MX"
                ),
                "status": "effective_preflight_passed",
                "authorized_model_id": model_id,
                "authorized_base_seed": base_seed,
            },
            "script": script,
            "source_code": [dict(script)],
            "outputs": output_records,
        }
        return manifest, one_portable, one_snapshot

    calibration_targets = projected.loc[
        projected["time_role"].eq("calibration_threshold")
        & projected["target_year_month"].between("2021-01", "2021-12")
    ].copy()
    assert len(calibration_targets) == 672
    calibration_metadata = pd.DataFrame(
        {
            "source_id": ["wqp"] * 224,
            "site_id": [f"calibration-site-{index:03d}" for index in range(224)],
            "common_origin_id": [
                f"calibration-origin-{index:03d}" for index in range(224)
            ],
            "assignment_role": ["development"] * 224,
            "time_role": ["calibration_threshold"] * 224,
            "origin_year_month": ["2020-12"] * 224,
        }
    )
    synthetic_bloom = np.resize(np.array([0.0, 1.0], dtype=np.float32), (224, 3))
    synthetic_risk = np.linspace(0.0, 1.0, 224 * 3, dtype=np.float32).reshape(
        224, 3
    )
    calibration_bundle = runner.anfis_training.TrainingBundle(
        metadata=calibration_metadata.reset_index(drop=True),
        x=np.zeros((224, 3, 2), dtype=np.float32),
        bloom=synthetic_bloom,
        risk=synthetic_risk,
    )
    prediction_arrays = (
        np.full((224, 3), 0.5),
        np.full((224, 3), 0.5),
        np.full((224, 3), -4.0),
    )
    with pytest.raises(
        runner.anfis_training.AnfisAblationTrainingError,
        match="another role",
    ):
        runner.anfis_training._selection_prediction_frame(
            calibration_bundle,
            model_id="A0",
            base_seed=1729,
            bloom_probability=prediction_arrays[0],
            risk_mu=prediction_arrays[1],
            risk_logvar=prediction_arrays[2],
        )
    direct_calibration_frame = runner._anfis_calibration_threshold_prediction_frame(
        calibration_bundle,
        model_id="A0",
        base_seed=1729,
        bloom_probability=prediction_arrays[0],
        risk_mu=prediction_arrays[1],
        risk_logvar=prediction_arrays[2],
    )
    assert len(direct_calibration_frame) == 672
    assert set(direct_calibration_frame["time_role"]) == {"calibration_threshold"}
    assert direct_calibration_frame["target_year_month"].between(
        "2021-01", "2021-12"
    ).all()
    wrong_role = direct_calibration_frame.copy()
    wrong_role["time_role"] = "model_selection"
    with pytest.raises(calibration.FinalCalibrationError, match="another role"):
        runner._canonical_anfis_calibration_threshold_prediction_frame(wrong_role)
    for column, poison in (
        ("model_id", np.str_("A0")),
        ("base_seed", 1729.0),
        ("base_seed", "1729"),
        ("horizon_months", True),
        ("observed_bloom", False),
        ("predicted_risk", 1),
        ("predicted_risk", "0.5"),
    ):
        poisoned_frame = direct_calibration_frame.copy()
        poisoned_frame[column] = poisoned_frame[column].astype(object)
        poisoned_frame.at[0, column] = poison
        with pytest.raises(calibration.FinalCalibrationError, match="cell type"):
            runner._canonical_anfis_calibration_threshold_prediction_frame(
                poisoned_frame
            )
    empty_site = direct_calibration_frame.copy()
    empty_site.at[0, "site_id"] = ""
    with pytest.raises(calibration.FinalCalibrationError, match="identity is empty"):
        runner._canonical_anfis_calibration_threshold_prediction_frame(empty_site)
    invalid_seed: Any = 1729.0
    with pytest.raises(calibration.FinalCalibrationError, match="unregistered"):
        runner._anfis_calibration_threshold_prediction_frame(
            calibration_bundle,
            model_id="A0",
            base_seed=invalid_seed,
            bloom_probability=prediction_arrays[0],
            risk_mu=prediction_arrays[1],
            risk_logvar=prediction_arrays[2],
        )
    fractional_bloom = calibration_bundle.bloom.copy()
    fractional_bloom[0, 0] = 0.5
    invalid_bundle = runner.anfis_training.TrainingBundle(
        metadata=calibration_bundle.metadata.copy(),
        x=calibration_bundle.x.copy(),
        bloom=fractional_bloom,
        risk=calibration_bundle.risk.copy(),
    )
    with pytest.raises(calibration.FinalCalibrationError, match="tensor values"):
        runner._anfis_calibration_threshold_prediction_frame(
            invalid_bundle,
            model_id="A0",
            base_seed=1729,
            bloom_probability=prediction_arrays[0],
            risk_mu=prediction_arrays[1],
            risk_logvar=prediction_arrays[2],
        )
    wrong_assignment = calibration_bundle.metadata.copy()
    wrong_assignment.at[0, "assignment_role"] = "holdout"
    invalid_bundle = runner.anfis_training.TrainingBundle(
        metadata=wrong_assignment,
        x=calibration_bundle.x.copy(),
        bloom=calibration_bundle.bloom.copy(),
        risk=calibration_bundle.risk.copy(),
    )
    with pytest.raises(calibration.FinalCalibrationError, match="metadata identity"):
        runner._anfis_calibration_threshold_prediction_frame(
            invalid_bundle,
            model_id="A0",
            base_seed=1729,
            bloom_probability=prediction_arrays[0],
            risk_mu=prediction_arrays[1],
            risk_logvar=prediction_arrays[2],
        )

    class FakeModel:
        def to(self, _device: Any) -> FakeModel:
            return self

        def load_state_dict(self, _state: Any, *, strict: bool) -> None:
            assert strict is True

    fake_torch = SimpleNamespace(device=lambda name: name)
    monkeypatch.setattr(runner, "_mcal_sequence_frame", sequence_input)
    monkeypatch.setattr(runner, "_torch_input", torch_input)
    monkeypatch.setattr(runner, "_json_input", json_input)
    monkeypatch.setattr(runner, "_equal_state_dicts", lambda *_: True)
    monkeypatch.setattr(runner, "_standardizer_from_payload", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        runner,
        "_calibration_bundle_from_sequence",
        lambda *_args, **_kwargs: calibration_bundle,
    )
    monkeypatch.setattr(runner.anfis_training, "_require_torch", lambda: fake_torch)
    monkeypatch.setattr(
        runner.anfis_training,
        "make_anfis_ablation_model",
        lambda **_: FakeModel(),
    )
    monkeypatch.setattr(
        runner.anfis_training,
        "_predict_arrays",
        lambda *_args, **_kwargs: prediction_arrays,
    )
    anfis_rows, anfis_records, anfis_snapshot = (
        runner._anfis_calibration_predictions(
            projected,
            authorized_dvc_pointers=authorized_pointers,
            repo_root=tmp_path,
        )
    )
    assert len(anfis_rows) == 2 * 5 * 672
    assert set(anfis_rows["model_id"]) == {"A0", "A1"}
    assert set(anfis_rows["time_role"]) == {"calibration_threshold"}
    assert sequence_calls == [("A0", 1729)] + [
        ("A1", seed) for seed in runner.REGISTERED_SEEDS
    ]
    assert len(anfis_records) == len(anfis_snapshot)
    assert inference_inputs
    assert all("state" not in path and "selection" not in path for _, path in inference_inputs)
    assert sum("_model_seed_" in role for role, _ in inference_inputs) == 10
    assert sum("_checkpoint_seed_" in role for role, _ in inference_inputs) == 10
    assert sum("_preprocessor_seed_" in role for role, _ in inference_inputs) == 10
    identity_drift["enabled"] = True
    inference_inputs.clear()
    with pytest.raises(calibration.FinalCalibrationError, match="model/checkpoint identity"):
        runner._anfis_calibration_predictions(
            projected,
            authorized_dvc_pointers=authorized_pointers,
            repo_root=tmp_path,
        )

    filter_evidence = _input_filter_evidence()
    assert len(filter_evidence[0]) == 16
    assert filter_evidence[0] == calibration.TARGET_FILTER_EVIDENCE_CONTRACT
    assert filter_evidence[1:] == [
        dict(record) for record in calibration.RAW_EXCLUSION_EVIDENCE_CONTRACT
    ]
    assert (
        calibration.EXCLUDED_TARGET_KEYS_SHA256
        == "e56ce749c2787097b878fc7a44350797521d143cbb08322c9537cdd905c0dfd9"
    )
    assert runner._validate_input_filter_evidence(filter_evidence) == filter_evidence
    assert [
        (
            record["model_id"],
            record["candidate_row_count"],
            record["matched_target_row_count"],
            record["excluded_incomplete_target_row_count"],
        )
        for record in filter_evidence[1:]
    ] == [
        ("B0", 4140, 2646, 1494),
        ("B1", 20700, 13230, 7470),
        ("B2", 20700, 13230, 7470),
        ("M0", 4140, 2646, 1494),
    ]
    assert {
        record["excluded_target_keys_sha256"] for record in filter_evidence[1:]
    } == {
        "e56ce749c2787097b878fc7a44350797521d143cbb08322c9537cdd905c0dfd9"
    }
    for field, value in (
        ("role", "target_predicate_scan"),
        ("materialized_row_count", 2646),
        ("materialized_row_count", 8743.0),
        ("projected_complete_target_row_count", 8743),
        ("outside_common_origin_projection_row_count", 6096),
        ("outside_common_origin_projection_row_count", True),
        ("row_count_equation", "8743=2646+6097"),
        ("development_site_count", 353),
        ("development_site_ids_sha256", "d" * 64),
        ("development_site_ids_sha256", int("1" * 64)),
    ):
        evidence_drift = [dict(record) for record in filter_evidence]
        evidence_drift[0][field] = value
        with pytest.raises(
            calibration.FinalCalibrationError,
            match="target filter evidence",
        ):
            runner._validate_input_filter_evidence(evidence_drift)
    for digest_drift in ("0" * 64, int("1" * 64), True):
        evidence_drift = [dict(record) for record in filter_evidence]
        evidence_drift[1]["excluded_target_keys_sha256"] = digest_drift
        with pytest.raises(
            calibration.FinalCalibrationError,
            match="raw exclusion evidence",
        ):
            runner._validate_input_filter_evidence(evidence_drift)
    for field, drift in (
        ("candidate_row_count", 4140.0),
        ("candidate_row_count", True),
        ("matched_target_row_count", "2646"),
        ("excluded_incomplete_target_row_count", 1494.0),
        ("model_id", 0),
        ("source_path", True),
    ):
        evidence_drift = [dict(record) for record in filter_evidence]
        evidence_drift[1][field] = drift
        with pytest.raises(
            calibration.FinalCalibrationError,
            match="raw exclusion evidence",
        ):
            runner._validate_input_filter_evidence(evidence_drift)
    historical = [dict(record) for record in filter_evidence]
    historical[1].update(
        {
            "candidate_row_count": 2931,
            "matched_target_row_count": 2646,
            "excluded_incomplete_target_row_count": 285,
        }
    )
    with pytest.raises(
        calibration.FinalCalibrationError,
        match="raw exclusion evidence drifted: B0",
    ):
        runner._validate_input_filter_evidence(historical)
    for evidence_drift in (
        filter_evidence[:-1],
        [*filter_evidence, dict(filter_evidence[-1])],
        [
            filter_evidence[0],
            filter_evidence[2],
            filter_evidence[1],
            *filter_evidence[3:],
        ],
    ):
        with pytest.raises(calibration.FinalCalibrationError):
            runner._validate_input_filter_evidence(evidence_drift)
    extra_field = [dict(record) for record in filter_evidence]
    extra_field[1]["unexpected"] = 0
    with pytest.raises(
        calibration.FinalCalibrationError,
        match="raw exclusion evidence drifted: B0",
    ):
        runner._validate_input_filter_evidence(extra_field)
    availability = _model_availability()
    authority = {
        "gate": calibration.PATCH_GATE,
        "status": "effective",
        "nonce": "stable",
        "authority_binding_sha256": "a" * 64,
    }
    payloads, manifest = runner.build_final_calibration_bundle(
        authority=authority,
        predictions=predictions,
        model_availability=availability,
        target_universe=target_universe,
        input_records=[{"path": "synthetic", "sha256": "0" * 64}],
        input_filter_evidence=filter_evidence,
        execution_policy=_calibration_execution_policy(),
        repo_root=tmp_path,
    )
    assert [path.relative_to(tmp_path).as_posix() for path, _ in payloads] == list(
        EXPECTED_OUTPUTS
    )
    assert payloads[-1][0] == tmp_path / EXPECTED_OUTPUTS[-1]
    assert json.loads(payloads[-1][1]) == manifest
    assert manifest["group_counts"] == {
        "bloom": 66,
        "ordinal": 33,
        "uncertainty": 30,
        "q_c": 90,
    }
    assert manifest["temporal_protocol"] == {
        "fit": "2019",
        "assessment": "2020",
        "refit_threshold_cutpoint_q_c": "2021",
        "time_column": "target_year_month",
    }
    assert manifest["scientific_boundary"] == {
        "development_only": True,
        "holdout_accessed": False,
        "post_2021_rows_accessed": False,
        "final_evaluation_run": False,
        "future_outcomes_accessed": False,
    }
    specs = json.loads(payloads[0][1])
    assert len(specs["bloom_calibrators"]) == 66
    assert len(specs["split_conformal_q_c"]) == 90
    b0_specs = [
        record for record in specs["bloom_calibrators"] if record["model_id"] == "B0"
    ]
    assert len(b0_specs) == 3
    for record in b0_specs:
        assert record["selected_method"] == "identity"
        assert record["refit_spec"] == {
            "method": "identity",
            "parameters": {},
            "fit_rows": 0,
        }
        assert record["refit_year"] is None
        assert record["refit_status"] == "not_applicable_fixed_identity"
    metrics = pd.read_csv(io.BytesIO(payloads[1][1]))
    thresholds = pd.read_csv(io.BytesIO(payloads[2][1]))
    ordinal = pd.read_csv(io.BytesIO(payloads[3][1]))
    availability_frame = pd.read_csv(io.BytesIO(payloads[4][1]))
    assert (len(metrics), len(thresholds), len(ordinal), len(availability_frame)) == (
        66,
        66,
        33,
        11,
    )
    assert thresholds["selection_year"].eq(2021).all()
    b0_ordinal = ordinal[ordinal["model_id"].eq("B0")]
    completed_ordinal = ordinal[ordinal["model_id"].isin(["B1", "B2"])]
    assert len(b0_ordinal) == 3
    assert b0_ordinal["status"].eq(
        "not_available_degenerate_constant_score"
    ).all()
    assert b0_ordinal["cutpoints"].isna().all()
    assert len(completed_ordinal) == 30
    assert completed_ordinal["status"].eq("completed").all()

    # Exercise the strict R-output parsers on real builder bytes.  Shape-only
    # JSON/CSV checks are insufficient here: order, canonical encoding,
    # cardinality, and the scientific selector semantics must all remain
    # independently closed after publication.
    payload_map = {
        Path(path.relative_to(tmp_path).as_posix()): payload
        for path, payload in payloads
    }
    indexed_specs = calibration._validate_calibrator_specs(specs)
    calibration._validate_calibration_csv_outputs(
        payload_map,
        calibrators=indexed_specs,
    )
    for specs_drift in (
        {**specs, "extra": False},
        {
            **specs,
            "bloom_calibrators": list(reversed(specs["bloom_calibrators"])),
        },
        {
            **specs,
            "split_conformal_q_c": specs["split_conformal_q_c"][:-1],
        },
    ):
        with pytest.raises(calibration.FinalCalibrationError):
            calibration._validate_calibrator_specs(specs_drift)
    for malformed_identity in (1729.0, True):
        identity_drift_payload = json.loads(json.dumps(specs))
        identity_drift_payload["bloom_calibrators"][0]["model_seed"] = (
            malformed_identity
        )
        with pytest.raises(calibration.FinalCalibrationError):
            calibration._validate_calibrator_specs(identity_drift_payload)

    wrong_specs = json.loads(json.dumps(specs))
    wrong_record = next(
        record
        for record in wrong_specs["bloom_calibrators"]
        if record["model_id"] != "B0"
    )
    minimum_brier = min(
        candidate["brier"] for candidate in wrong_record["selection_candidates"]
    )
    retained = [
        candidate
        for candidate in wrong_record["selection_candidates"]
        if candidate["brier"] <= minimum_brier + 0.001
    ]
    selected_candidate = min(
        retained,
        key=lambda candidate: (
            candidate["ece10"],
            candidate["simplicity_rank"],
        ),
    )
    assert wrong_record["selected_method"] == selected_candidate["method"]
    wrong_candidate = next(
        candidate
        for candidate in wrong_record["selection_candidates"]
        if candidate["method"] != selected_candidate["method"]
    )
    wrong_method = wrong_candidate["method"]
    wrong_record["selected_method"] = wrong_method
    wrong_parameters: dict[str, Any]
    if wrong_method == "identity":
        wrong_parameters = {}
    elif wrong_method == "platt_logistic":
        wrong_parameters = {"coefficient": 1.0, "intercept": 0.0}
    else:
        wrong_parameters = {
            "out_of_bounds": "clip",
            "x_thresholds": [0.0, 1.0],
            "y_thresholds": [0.0, 1.0],
        }
    wrong_record["refit_spec"] = {
        "method": wrong_method,
        "parameters": wrong_parameters,
        "fit_rows": 224,
    }
    with pytest.raises(calibration.FinalCalibrationError):
        calibration._validate_calibrator_specs(wrong_specs)

    metrics_path = calibration.CALIBRATION_METRICS_PATH
    threshold_path = calibration.ALERT_THRESHOLDS_PATH
    for path, drifted_payload in (
        (metrics_path, payload_map[metrics_path].replace(b"\n", b"\r\n")),
        (
            metrics_path,
            _rewrite_csv(
                payload_map[metrics_path],
                lambda table: table.__setitem__(
                    slice(1, None), list(reversed(table[1:]))
                ),
            ),
        ),
        (
            metrics_path,
            _rewrite_csv(payload_map[metrics_path], lambda table: table.pop()),
        ),
        (
            threshold_path,
            _rewrite_csv(
                payload_map[threshold_path],
                lambda table: table[1].__setitem__(
                    table[0].index("threshold"), "2"
                ),
            ),
        ),
        (
            metrics_path,
            _rewrite_csv(
                payload_map[metrics_path],
                lambda table: table[1].__setitem__(
                    table[0].index("model_seed"), "1729.0"
                ),
            ),
        ),
        (
            metrics_path,
            _rewrite_csv(
                payload_map[metrics_path],
                lambda table: table[1].__setitem__(
                    table[0].index("horizon_months"), "True"
                ),
            ),
        ),
        (
            threshold_path,
            _rewrite_csv(
                payload_map[threshold_path],
                lambda table: table[1].__setitem__(
                    table[0].index("f2"), "0.123"
                ),
            ),
        ),
    ):
        drifted_payloads = {**payload_map, path: drifted_payload}
        with pytest.raises(calibration.FinalCalibrationError):
            calibration._validate_calibration_csv_outputs(
                drifted_payloads,
                calibrators=indexed_specs,
            )

    # A coherent selector forgery updates the chosen method, its refit spec,
    # the matching metrics values, and every byte/hash binding.  The loader
    # must still reject it because the winner is determined by the sealed
    # Brier tolerance -> ECE -> simplicity rule, not by self-consistent claims.
    wrong_identity = (
        str(wrong_record["model_id"]),
        str(wrong_record["model_seed"]),
        str(wrong_record["horizon_months"]),
    )

    def forge_metrics(table: list[list[str]]) -> None:
        header = table[0]
        for row in table[1:]:
            if tuple(row[header.index(column)] for column in (
                "model_id",
                "model_seed",
                "horizon_months",
            )) == wrong_identity:
                row[header.index("selected_method")] = wrong_method
                row[header.index("selection_brier")] = format(
                    float(wrong_candidate["brier"]), ".17g"
                )
                row[header.index("selection_ece10")] = format(
                    float(wrong_candidate["ece10"]), ".17g"
                )
                return
        pytest.fail("synthetic selector identity was not found in metrics")

    forged_payloads = dict(payload_map)
    forged_payloads[calibration.CALIBRATOR_SPECS_PATH] = (
        runner._canonical_json_bytes(wrong_specs)
    )
    forged_payloads[metrics_path] = _rewrite_csv(
        payload_map[metrics_path], forge_metrics
    )
    input_records = [{"path": "synthetic", "sha256": "0" * 64}]
    monkeypatch.setattr(
        calibration,
        "_scientific_input_inventory",
        lambda **_: {
            "calibration_required_inputs": input_records,
            "e7_required_inputs": [],
        },
    )
    monkeypatch.setattr(
        calibration,
        "_effective_authority_binding_sha256",
        lambda **_: "a" * 64,
    )
    for relative, payload in payload_map.items():
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        destination.chmod(0o644)
    assert calibration._require_exact_output_group(
        calibration.CALIBRATION_OUTPUT_PATHS,
        manifest_path=calibration.FINAL_CALIBRATION_MANIFEST_PATH,
        repo_root=tmp_path,
        context="calibration",
    ) == 6
    forged_manifest = json.loads(json.dumps(manifest))
    for output in forged_manifest["outputs"]:
        relative = Path(output["path"])
        if relative in forged_payloads:
            output["bytes"] = len(forged_payloads[relative])
            output["sha256"] = hashlib.sha256(
                forged_payloads[relative]
            ).hexdigest()
    forged_payloads[calibration.FINAL_CALIBRATION_MANIFEST_PATH] = (
        runner._canonical_json_bytes(forged_manifest)
    )
    for relative in (
        calibration.CALIBRATOR_SPECS_PATH,
        metrics_path,
        calibration.FINAL_CALIBRATION_MANIFEST_PATH,
    ):
        (tmp_path / relative).write_bytes(forged_payloads[relative])
    with pytest.raises(calibration.FinalCalibrationError):
        calibration._require_exact_output_group(
            calibration.CALIBRATION_OUTPUT_PATHS,
            manifest_path=calibration.FINAL_CALIBRATION_MANIFEST_PATH,
            repo_root=tmp_path,
            context="calibration",
        )
    for relative in calibration.CALIBRATION_OUTPUT_PATHS:
        (tmp_path / relative).unlink()

    for column, value in (
        ("assignment_role", "holdout"),
        ("target_year_month", "2022-01"),
        ("target_year_month", "2021-13"),
        ("origin_year_month", None),
        ("model_seed", 1729.5),
        ("model_seed", True),
        ("model_seed", "1729"),
        ("horizon_months", 1.5),
        ("horizon_months", True),
        ("horizon_months", "1"),
        ("bloom_probability", float("nan")),
        ("bloom_probability", float("inf")),
        ("bloom_probability", 1.1),
        ("bloom_probability", True),
        ("bloom_probability", "0.5"),
        ("bloom_label", True),
    ):
        drift = predictions.copy()
        if column in {"model_seed", "horizon_months"}:
            drift[column] = (
                drift[column].astype("float64")
                if type(value) is float
                else drift[column].astype(object)
            )
        elif type(value) in {bool, str}:
            drift[column] = drift[column].astype(object)
        drift.loc[0, column] = value
        with pytest.raises(calibration.FinalCalibrationError):
            runner.build_final_calibration_bundle(
                authority=authority,
                predictions=drift,
                model_availability=availability,
                target_universe=target_universe,
                input_filter_evidence=filter_evidence,
                repo_root=tmp_path,
            )
    a0_index = predictions.index[predictions["model_id"].eq("A0")][0]
    for column, value in (
        ("bloom_label", 1 - int(predictions.loc[a0_index, "bloom_label"])),
        ("observed_risk", 0.25),
    ):
        target_drift = predictions.copy()
        target_drift.loc[a0_index, column] = value
        with pytest.raises(calibration.FinalCalibrationError):
            runner.build_final_calibration_bundle(
                authority=authority,
                predictions=target_drift,
                model_availability=availability,
                target_universe=target_universe,
                input_filter_evidence=filter_evidence,
                repo_root=tmp_path,
            )
    duplicate = pd.concat([predictions, predictions.iloc[[0]]], ignore_index=True)
    with pytest.raises(calibration.FinalCalibrationError):
        runner.build_final_calibration_bundle(
            authority=authority,
            predictions=duplicate,
            model_availability=availability,
            target_universe=target_universe,
            input_filter_evidence=filter_evidence,
            repo_root=tmp_path,
        )
    first_group = (
        predictions["model_id"].eq("B0")
        & predictions["model_seed"].eq(1729)
        & predictions["horizon_months"].eq(1)
    )
    missing_target = predictions.drop(predictions.index[first_group][0])
    extra_target = pd.concat(
        [predictions, predictions.loc[[predictions.index[first_group][0]]].assign(
            site_id="site-extra",
            common_origin_id="wqp:1:2019:extra",
        )],
        ignore_index=True,
    )
    swapped_target = predictions.copy()
    swapped_target.loc[predictions.index[first_group][0], "site_id"] = "site-swapped"
    swapped_target.loc[
        predictions.index[first_group][0], "common_origin_id"
    ] = "wqp:1:2019:swapped"
    for drift in (missing_target, extra_target, swapped_target):
        with pytest.raises(calibration.FinalCalibrationError):
            runner.build_final_calibration_bundle(
                authority=authority,
                predictions=drift,
                model_availability=availability,
                target_universe=target_universe,
                input_filter_evidence=filter_evidence,
                repo_root=tmp_path,
            )
    globally_wrong = predictions.copy()
    wrong_key = (
        globally_wrong["horizon_months"].eq(1)
        & globally_wrong["target_year_month"].eq("2019-01")
        & globally_wrong["site_id"].eq("site-00")
    )
    globally_wrong.loc[wrong_key, "site_id"] = "site-globally-wrong"
    with pytest.raises(calibration.FinalCalibrationError):
        runner._validate_calibration_frame(
            globally_wrong,
            target_universe=target_universe,
        )
    for field, value in (
        ("availability_reason", "drift"),
        ("seed_policy", "drift"),
        ("seeds", [True]),
        ("horizons_months", [1, 2]),
        ("selected_family", True),
        ("bloom_calibration", "drift"),
    ):
        matrix_drift = [dict(record) for record in availability]
        matrix_drift[0][field] = value
        with pytest.raises(calibration.FinalCalibrationError):
            runner.build_final_calibration_bundle(
                authority=authority,
                predictions=predictions,
                model_availability=matrix_drift,
                target_universe=target_universe,
                input_filter_evidence=filter_evidence,
                repo_root=tmp_path,
            )

    events: list[str] = []
    authority_box: dict[str, Any] = {"value": authority}
    stable_snapshot = [{"path": "synthetic", "sha256": "0" * 64}]
    snapshot_box: dict[str, Any] = {"current": stable_snapshot}

    def require(*, verify_remote: bool, repo_root: Path) -> Mapping[str, Any]:
        assert verify_remote is True and repo_root == tmp_path
        events.append("gate")
        value = authority_box["value"]
        if isinstance(value, list):
            value = value.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value

    def load(
        *, authorized_dvc_pointers: Any, repo_root: Path
    ) -> dict[str, Any]:
        assert repo_root == tmp_path
        assert authorized_dvc_pointers == authorized_pointers
        events.append("load")
        return {
            "predictions": predictions,
            "model_availability": availability,
            "input_records": [{"path": "synthetic", "sha256": "0" * 64}],
            "input_snapshot": [dict(record) for record in stable_snapshot],
            "target_universe": target_universe,
            "input_filter_evidence": filter_evidence,
        }

    def revalidate(
        snapshot: Any,
        *,
        authorized_dvc_pointers: Any,
        repo_root: Path,
    ) -> None:
        assert repo_root == tmp_path
        assert authorized_dvc_pointers == authorized_pointers
        events.append("snapshot")
        if snapshot != snapshot_box["current"]:
            raise calibration.FinalCalibrationError("input snapshot changed")

    def cpu_policy(*, repo_root: Path) -> dict[str, Any]:
        assert repo_root == tmp_path
        events.append("cpu")
        return _calibration_execution_policy()

    def validate_inventory(
        observed_authority: Mapping[str, Any], records: Any
    ) -> None:
        assert observed_authority is authority or observed_authority == authority
        assert records == [{"path": "synthetic", "sha256": "0" * 64}]
        events.append("inventory")

    monkeypatch.setattr(
        calibration, "require_final_calibration_authority", require
    )
    monkeypatch.setattr(
        runner,
        "_authorized_scientific_dvc_pointers",
        lambda _authority: authorized_pointers,
    )
    monkeypatch.setattr(runner, "_load_final_calibration_inputs", load)
    monkeypatch.setattr(runner, "_configure_calibration_cpu_policy", cpu_policy)
    monkeypatch.setattr(
        runner, "_validate_authority_input_inventory", validate_inventory
    )
    monkeypatch.setattr(
        runner, "_revalidate_final_calibration_input_snapshot", revalidate
    )
    authority_box["value"] = calibration.FinalCalibrationError("gate")
    with pytest.raises(calibration.FinalCalibrationError, match="gate"):
        runner.execute_one_shot(repo_root=tmp_path)
    assert events == ["gate"]
    assert all(not path.exists() for path in _relative_outputs(tmp_path))

    authority_box["value"] = authority
    namespace_cases = (
        _relative_outputs(tmp_path)[:1],
        _relative_outputs(tmp_path),
        (tmp_path / runner.GUARD_PATH.relative_to(runner.PROJECT_ROOT),),
    )
    for occupied in namespace_cases:
        for path in occupied:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"foreign\n")
        events.clear()
        with pytest.raises(
            calibration.FinalCalibrationError,
            match="namespace|exists|guard|partial|malformed",
        ):
            runner.execute_one_shot(repo_root=tmp_path)
        assert events == ["gate"]
        for path in occupied:
            assert path.read_bytes() == b"foreign\n"
            path.unlink()

    authority_box["value"] = [authority, {**authority, "nonce": "drift"}]
    events.clear()
    with pytest.raises(calibration.FinalCalibrationError, match="authority|changed"):
        runner.execute_one_shot(repo_root=tmp_path)
    assert events[0:4] == ["gate", "cpu", "load", "inventory"]
    assert events.count("gate") == 2
    assert all(not path.exists() for path in _relative_outputs(tmp_path))

    authority_box["value"] = authority
    snapshot_box["current"] = [{"path": "synthetic", "sha256": "1" * 64}]
    events.clear()
    with pytest.raises(calibration.FinalCalibrationError, match="snapshot changed"):
        runner.execute_one_shot(repo_root=tmp_path)
    assert events[0:5] == ["gate", "cpu", "load", "inventory", "snapshot"]
    assert all(not path.exists() for path in _relative_outputs(tmp_path))

    authority_box["value"] = authority
    snapshot_box["current"] = stable_snapshot
    events.clear()
    result = runner.execute_one_shot(repo_root=tmp_path)
    assert events[0:4] == ["gate", "cpu", "load", "inventory"]
    assert events.count("gate") >= 2
    assert events.count("snapshot") >= 2
    assert result["status"] == "completed_unpublished"
    assert result["output_count"] == 6
    assert [record["path"] for record in result["records"]] == list(EXPECTED_OUTPUTS)
    assert all(path.is_file() for path in _relative_outputs(tmp_path))
    assert json.loads(_relative_outputs(tmp_path)[-1].read_bytes()) == result["manifest"]
