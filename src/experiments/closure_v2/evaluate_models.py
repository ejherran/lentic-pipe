#!/usr/bin/env python
"""Run the sealed Closure V2 benchmark without refitting or recalibrating.

The command has three modes.  The default mode is input-only and performs no
writes.  ``--execute`` consumes the one-shot activation, reads target values,
and publishes the physical prediction table plus the lightweight benchmark
tables.  ``--finalize`` is run only after ``dvc add`` and writes the completion
manifest last.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import io
import json
import math
import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq
import yaml
from sklearn.metrics import (
    average_precision_score,
    cohen_kappa_score,
    f1_score,
    precision_score,
    recall_score,
)

from src.experiments import closure_phase3_context as phase3
from src.experiments.calibrate_closure_final_models import apply_calibrator_spec
from src.experiments.closure_contract import ClosureContractError, load_json_mapping
from src.experiments.closure_v2.activate_evaluation import (
    OUTCOME_LOG,
    _canonical_line,
    _parse_log,
    load_effective_activation,
)
from src.experiments.closure_v2.audit_v1_inputs import PROJECT_ROOT
from src.experiments.closure_v2.build_eligibility import EXPECTED_SEEDS, INPUT_COLUMNS
from src.experiments.closure_v2.calibrate_temporal import (
    _irc_probability,
    _load_model,
    recursive_predictions,
)
from src.experiments.closure_v2.hashing import (
    canonical_json_bytes,
    file_record,
    md5_file,
    sha256_file,
)
from src.experiments.closure_v2.lock_models import (
    MODEL_LOCK_MANIFEST_PATH,
    MODEL_LOCK_PATH,
    MODEL_LOCK_TAG,
)
from src.fuzzy.expert import (
    nutrient_pressure,
    physicochemical_condition,
    thermal_biological_favorability,
)


SCRIPT_PATH = Path("src/experiments/closure_v2/evaluate_models.py")
INPUT_MANIFEST = Path("reports/closure_v2/01_surface/locked_evaluation_input_manifest.json")
TARGETS_PATH = Path("data/targets/monthly_targets_model_v0.parquet")
CALIBRATOR_PATH = Path("reports/closure_v2/03_calibration/calibrator_specs.json")
THRESHOLD_PATH = Path("reports/closure_v2/03_calibration/alert_thresholds.csv")
CONFORMAL_PATH = Path("reports/closure_v2/03_calibration/conformal_quantiles.csv")
FRESH_ROOT = Path("data/closure_v2/locked_evaluation")
PREDICTIONS_PATH = Path("data/closure_v2/predictions_long.parquet")
PREDICTIONS_POINTER = Path("data/closure_v2/predictions_long.parquet.dvc")
OUTPUT_ROOT = Path("reports/closure_v2/04_evaluation")
METRICS_PATH = OUTPUT_ROOT / "model_metrics_long.csv"
AVAILABILITY_PATH = OUTPUT_ROOT / "model_availability.csv"
FUNNEL_PATH = OUTPUT_ROOT / "intent_to_predict_funnel.csv"
PAIRWISE_PATH = OUTPUT_ROOT / "pairwise_common_rows.csv"
SENSITIVITY_PATH = OUTPUT_ROOT / "threshold_sensitivity.csv"
UNCERTAINTY_PATH = OUTPUT_ROOT / "uncertainty_ledger.csv"
REPORT_PATH = OUTPUT_ROOT / "BENCHMARK_REPORT.md"
MANIFEST_PATH = OUTPUT_ROOT / "evaluation_manifest.json"
LIGHT_PATHS = (
    METRICS_PATH,
    AVAILABILITY_PATH,
    FUNNEL_PATH,
    PAIRWISE_PATH,
    SENSITIVITY_PATH,
    UNCERTAINTY_PATH,
    REPORT_PATH,
)
ALL_FINAL_PATHS = (PREDICTIONS_PATH, PREDICTIONS_POINTER, *LIGHT_PATHS, MANIFEST_PATH)
HORIZONS = (1, 2, 3)
PRIMARY_MODELS = ("P1", "B2", "P0")
COMPARISONS = (
    ("P1_vs_B2", "P1", "B2", "primary"),
    ("P1_vs_P0", "P1", "P0", "primary"),
    ("P1_vs_B1", "P1", "B1", "secondary"),
    ("P1_vs_A1", "P1", "A1", "secondary"),
    ("A1_vs_A0", "A1", "A0", "secondary"),
    ("M0_vs_P1", "M0", "P1", "secondary"),
)
SENSITIVITY_CUTOFFS = (25.0, 30.0, 33.0, 50.0)
STATE_COLUMNS = (
    "yN", "yF", "yT", "sigma_N", "sigma_F", "sigma_T",
    "delta_yN", "delta_yF", "delta_yT",
)
PREDICTION_COLUMNS = (
    "evaluation_cohort", "model_id", "base_seed", "aggregation_level",
    "origin_id", "source_id", "site_id", "origin_year_month",
    "target_year_month", "horizon_months", "intent_to_predict",
    "input_eligible", "prediction_status", "failure_reason",
    "prediction_successful", "target_month_exists", "target_available",
    "metric_evaluable", "shared_success", "bloom_probability",
    "alert_threshold", "predicted_alert", "predicted_risk_chla",
    "predicted_risk_sigma", "risk_interval_lower_90", "risk_interval_upper_90",
    "future_chlorophyll_a_ugL", "bloom_h", "target_risk_chla_h",
    "target_trophic_state_h", "outcome_bloom_25", "outcome_bloom_30",
    "outcome_bloom_33", "outcome_bloom_50", "result_state",
)
PREEXECUTION_IMPLEMENTATION_PATHS = {
    "data/closure_v2/.gitignore",
    "src/experiments/closure_v2/evaluate_models.py",
    "tests/closure_v2/test_evaluate_models.py",
    "tests/closure_v2/test_evaluation_guard.py",
}


class EvaluationError(ClosureContractError):
    """Raised when the sealed evaluation contract is crossed."""


def _git(*args: str, root: Path = PROJECT_ROOT) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _require_regular(root: Path, relative: Path) -> Path:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise EvaluationError(f"Required regular file is absent: {relative}")
    return path


def _git_bytes(commit: str, relative: Path, *, root: Path) -> bytes:
    return subprocess.run(
        ["git", "show", f"{commit}:{relative.as_posix()}"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout


def _validate_model_lock(root: Path) -> dict[str, Any]:
    if _git("cat-file", "-t", f"refs/tags/{MODEL_LOCK_TAG}", root=root) != "tag":
        raise EvaluationError("Model lock tag is not annotated")
    commit = _git("rev-parse", f"{MODEL_LOCK_TAG}^{{}}", root=root)
    head = _git("rev-parse", "HEAD", root=root)
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, head], cwd=root, check=False
    ).returncode != 0:
        raise EvaluationError("Model lock is not an ancestor of the evaluation HEAD")
    for relative in (MODEL_LOCK_PATH, MODEL_LOCK_MANIFEST_PATH):
        path = _require_regular(root, relative)
        if path.read_bytes() != _git_bytes(commit, relative, root=root):
            raise EvaluationError(f"Live model-lock authority drifted: {relative}")
    lock = load_json_mapping(root / MODEL_LOCK_PATH)
    if lock.get("status") != "locked_unpublished" or lock.get("manifest_written_last") is not True:
        raise EvaluationError("Model lock is incomplete")
    authorization = lock.get("authorization")
    if not isinstance(authorization, Mapping) or any(
        authorization.get(key) is not False
        for key in ("evaluation_authorized", "refit_authorized", "recalibration_authorized")
    ):
        raise EvaluationError("Frozen model-lock authorization drifted")
    models = lock.get("models")
    if not isinstance(models, list) or len(models) != 10:
        raise EvaluationError("Model-lock slot registry drifted")
    for record in models:
        if not isinstance(record, Mapping) or record.get("availability") != "available":
            raise EvaluationError("A registered temporal model is unavailable")
        for key in ("model", "checkpoint", "slot_manifest"):
            artifact = record.get(key)
            if not isinstance(artifact, Mapping):
                raise EvaluationError("Model-lock artifact record is malformed")
            relative = Path(str(artifact.get("path")))
            path = _require_regular(root, relative)
            if path.stat().st_size != artifact.get("bytes") or sha256_file(path) != artifact.get("sha256"):
                raise EvaluationError(f"Locked model artifact drifted: {relative}")
    return {"commit": commit, "sha256": sha256_file(root / MODEL_LOCK_PATH), "slots": 10}


def _validate_fresh_inputs(root: Path) -> dict[str, Any]:
    manifest = load_json_mapping(_require_regular(root, INPUT_MANIFEST))
    expected = {
        "status": "completed",
        "evaluation_cohort": "fresh_primary",
        "selected_route": "fresh_location",
        "candidate_location_count": 137,
        "intent_origins_per_horizon": 2286,
        "outcome_values_opened": False,
        "target_availability_inspected": False,
        "replacement_used": False,
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise EvaluationError("Fresh input manifest drifted")
    records = manifest.get("data_artifacts")
    if not isinstance(records, list) or len(records) != 4:
        raise EvaluationError("Fresh input artifact registry drifted")
    for record in records:
        if not isinstance(record, Mapping):
            raise EvaluationError("Fresh input artifact record is malformed")
        path = _require_regular(root, Path(str(record.get("path"))))
        pointer = _require_regular(root, Path(str(record.get("dvc_pointer"))))
        if (
            path.stat().st_size != record.get("bytes")
            or sha256_file(path) != record.get("sha256")
            or pointer.stat().st_size != record.get("dvc_pointer_bytes")
            or sha256_file(pointer) != record.get("dvc_pointer_sha256")
        ):
            raise EvaluationError("Fresh input physical binding drifted")
    return {"locations": 137, "origins": 2286, "manifest_sha256": sha256_file(root / INPUT_MANIFEST)}


def validate_authority(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    activation = load_effective_activation(root=root)
    if activation["executions_remaining"] != 1 or activation["outcome_access_authorized"] is not True:
        raise EvaluationError("One-shot evaluation activation is not available")
    if _git("rev-parse", "HEAD", root=root) != _git("rev-parse", "origin/closure-v2", root=root):
        raise EvaluationError("Evaluation HEAD and origin/closure-v2 must coincide")
    changed = {
        value
        for command in (("diff", "--name-only"), ("diff", "--cached", "--name-only"), ("ls-files", "--others", "--exclude-standard"))
        for value in _git(*command, root=root).splitlines()
        if value
    }
    if not changed.issubset(PREEXECUTION_IMPLEMENTATION_PATHS):
        raise EvaluationError(f"Unexpected pre-execution worktree changes: {sorted(changed - PREEXECUTION_IMPLEMENTATION_PATHS)}")
    model_lock = _validate_model_lock(root)
    fresh = _validate_fresh_inputs(root)
    if activation["activation_base_commit"] == model_lock["commit"]:
        raise EvaluationError("Fresh inputs must be published after the model lock")
    return {
        "status": "ready_to_evaluate",
        "head": _git("rev-parse", "HEAD", root=root),
        "activation": activation,
        "model_lock": model_lock,
        "fresh_primary": fresh,
        "refit_performed": False,
        "recalibration_performed": False,
        "writes_performed": False,
        "outcomes_opened": False,
    }


def _normalize_legacy(
    intents: pd.DataFrame, history: pd.DataFrame, origins: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    values = []
    for frame in (intents, history, origins):
        copy = frame.copy()
        copy["evaluation_cohort"] = "legacy_posthoc"
        copy["cohort_route"] = "v1_internal_holdout_reuse"
        values.append(copy)
    return cast(tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame], tuple(values))


def _load_cohorts(root: Path) -> dict[str, tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
    legacy = _normalize_legacy(*phase3._load_input_frames(root))
    fresh = (
        pq.read_table(_require_regular(root, FRESH_ROOT / "intent_origins.parquet")).to_pandas(),
        pq.read_table(_require_regular(root, FRESH_ROOT / "input_history.parquet")).to_pandas(),
        pq.read_table(_require_regular(root, FRESH_ROOT / "origin_features.parquet")).to_pandas(),
    )
    if len(fresh[0]) != 2286 or len(fresh[1]) != 27432 or len(fresh[2]) != 2286:
        raise EvaluationError("Fresh input denominators drifted")
    return {"legacy_posthoc": legacy, "fresh_primary": fresh}


def _expert_states(monthly: pd.DataFrame) -> pd.DataFrame:
    frame = monthly.copy()
    y_n, sigma_n, _ = nutrient_pressure(frame)
    y_f, sigma_f, _ = physicochemical_condition(frame)
    _, _, y_t, sigma_t, _ = thermal_biological_favorability(frame)
    state = frame[["source_id", "site_id", "year_month", "row_present"]].copy()
    for name, values in (
        ("yN", y_n), ("yF", y_f), ("yT", y_t),
        ("sigma_N", sigma_n), ("sigma_F", sigma_f), ("sigma_T", sigma_t),
    ):
        state[name] = np.asarray(values, dtype=np.float64)
    state = state.sort_values(["source_id", "site_id", "year_month"], kind="stable").reset_index(drop=True)
    prior = state.groupby(["source_id", "site_id"], sort=False)[
        ["year_month", "row_present", "yN", "yF", "yT"]
    ].shift(1)
    current_period = pd.PeriodIndex(state["year_month"], freq="M")
    prior_period = pd.PeriodIndex(prior["year_month"].fillna("1900-01"), freq="M")
    exact = (
        (current_period.asi8 - prior_period.asi8 == 1)
        & state["row_present"].astype(bool).to_numpy()
        & prior["row_present"].fillna(False).astype(bool).to_numpy()
    )
    for channel in ("yN", "yF", "yT"):
        delta = state[channel].to_numpy(dtype=np.float64) - pd.to_numeric(
            prior[channel], errors="coerce"
        ).to_numpy(dtype=np.float64)
        delta[~exact] = 0.0
        state[f"delta_{channel}"] = delta
    return state


def _sequence_frame(
    intents: pd.DataFrame, history: pd.DataFrame, states: pd.DataFrame
) -> tuple[pd.DataFrame, np.ndarray]:
    ordered_intents = intents.sort_values(
        ["source_id", "site_id", "origin_year_month", "origin_id"], kind="stable"
    ).reset_index(drop=True)
    ordered_history = history.sort_values(
        ["source_id", "site_id", "origin_year_month", "history_offset_months"], kind="stable"
    ).reset_index(drop=True)
    if len(ordered_history) != len(ordered_intents) * 12:
        raise EvaluationError("Evaluation history does not contain 12 rows per intent")
    ids = ordered_history["origin_id"].astype(str).to_numpy().reshape(len(ordered_intents), 12)
    if not np.all(ids == ordered_intents["origin_id"].astype(str).to_numpy()[:, None]):
        raise EvaluationError("Evaluation history order drifted")
    keys = ordered_history[["source_id", "site_id", "history_year_month"]].rename(
        columns={"history_year_month": "year_month"}
    )
    joined = keys.merge(
        states[["source_id", "site_id", "year_month", *STATE_COLUMNS]],
        on=["source_id", "site_id", "year_month"], how="left", validate="many_to_one", sort=False,
    )
    season = ordered_history[list(phase3.SEASON_COLUMNS)].apply(pd.to_numeric, errors="coerce")
    values = np.column_stack([joined[list(STATE_COLUMNS)].to_numpy(dtype=np.float64), season.to_numpy(dtype=np.float64)])
    cube = values.reshape(len(ordered_intents), 12, 13)
    present = ordered_history["row_present"].astype(bool).to_numpy().reshape(len(ordered_intents), 12)
    valid = (
        ordered_intents["base_input_status"].astype(str).eq("eligible").to_numpy()
        & present.all(axis=1)
        & np.isfinite(cube).all(axis=(1, 2))
    )
    selected = ordered_intents[[
        "origin_id", "source_id", "site_id", "evaluation_cohort", "origin_year_month",
        "base_input_status", "base_input_reason",
    ]].copy()
    for index, column in enumerate(INPUT_COLUMNS):
        selected[column] = [row.copy() for row in cube[:, :, index]]
    return selected, valid


def _load_calibration(root: Path) -> tuple[dict[tuple[str, int, int], Mapping[str, Any]], dict[tuple[str, int, int], float], dict[tuple[str, int, int, str], float]]:
    payload = load_json_mapping(_require_regular(root, CALIBRATOR_PATH))
    groups = payload.get("groups")
    if not isinstance(groups, list) or len(groups) != 30:
        raise EvaluationError("V2 calibrator registry drifted")
    specs: dict[tuple[str, int, int], Mapping[str, Any]] = {}
    for record in groups:
        if not isinstance(record, Mapping) or not isinstance(record.get("spec"), Mapping):
            raise EvaluationError("V2 calibrator record is malformed")
        key = (str(record["model_id"]), int(record["base_seed"]), int(record["horizon_months"]))
        specs[key] = cast(Mapping[str, Any], record["spec"])
    thresholds_frame = pd.read_csv(_require_regular(root, THRESHOLD_PATH))
    thresholds = {
        (str(model), int(seed), int(horizon)): float(threshold)
        for model, seed, horizon, threshold in thresholds_frame[
            ["model_id", "base_seed", "horizon_months", "threshold"]
        ].itertuples(index=False, name=None)
    }
    conformal_frame = pd.read_csv(_require_regular(root, CONFORMAL_PATH))
    conformal = {
        (str(model), int(seed), int(horizon), str(target)): float(quantile)
        for model, seed, horizon, target, coverage, quantile in conformal_frame[
            ["model_id", "base_seed", "horizon_months", "target", "coverage", "quantile"]
        ].itertuples(index=False, name=None)
        if float(coverage) == 0.90 and str(target) in {"yN", "yF", "yT"}
    }
    if len(specs) != 30 or len(thresholds) != 30 or len(conformal) != 90:
        raise EvaluationError("V2 calibration key coverage drifted")
    return specs, thresholds, conformal


def _empty_score(count: int) -> dict[str, np.ndarray]:
    shape = (count, 3)
    return {
        "valid": np.zeros(shape, dtype=bool),
        "bloom": np.full(shape, np.nan),
        "risk": np.full(shape, np.nan),
        "sigma": np.full(shape, np.nan),
        "lower": np.full(shape, np.nan),
        "upper": np.full(shape, np.nan),
        "threshold": np.full(shape, np.nan),
    }


def _temporal_scores(
    model_id: str,
    seed: int,
    selected: pd.DataFrame,
    valid: np.ndarray,
    specs: Mapping[tuple[str, int, int], Mapping[str, Any]],
    thresholds: Mapping[tuple[str, int, int], float],
    conformal: Mapping[tuple[str, int, int, str], float],
    *,
    root: Path,
) -> dict[str, np.ndarray]:
    result = _empty_score(len(selected))
    indices = np.flatnonzero(valid)
    if not len(indices):
        return result
    model, blend, _ = _load_model(model_id, seed, root=root)
    predictions = recursive_predictions(selected.iloc[indices].reset_index(drop=True), model, blend)
    for horizon in HORIZONS:
        state, state_sigma = predictions[horizon]
        raw = _irc_probability(state)
        probability = apply_calibrator_spec(specs[(model_id, seed, horizon)], raw)
        weights = np.asarray([0.5, -0.5, 2.0], dtype=np.float64) / 3.0
        risk_sigma = np.sqrt(np.sum((state_sigma[:, :3] * weights[None, :]) ** 2, axis=1))
        qn = conformal[(model_id, seed, horizon, "yN")]
        qf = conformal[(model_id, seed, horizon, "yF")]
        qt = conformal[(model_id, seed, horizon, "yT")]
        lower_state = state[:, :3].copy()
        upper_state = state[:, :3].copy()
        lower_state[:, 0] -= qn; lower_state[:, 1] += qf; lower_state[:, 2] -= qt
        upper_state[:, 0] += qn; upper_state[:, 1] -= qf; upper_state[:, 2] += qt
        column = horizon - 1
        result["valid"][indices, column] = True
        result["bloom"][indices, column] = probability
        result["risk"][indices, column] = raw
        result["sigma"][indices, column] = risk_sigma
        result["lower"][indices, column] = _irc_probability(lower_state)
        result["upper"][indices, column] = _irc_probability(upper_state)
        result["threshold"][indices, column] = thresholds[(model_id, seed, horizon)]
    return result


def _state_score(values: np.ndarray) -> np.ndarray:
    return np.clip((0.5 * values[:, 0] + 0.5 * (1.0 - values[:, 1]) + 2.0 * values[:, 2]) / 3.0, 0.0, 1.0)


def _current_state_scores(
    selected: pd.DataFrame,
    valid: np.ndarray,
    states: pd.DataFrame,
) -> dict[str, np.ndarray]:
    result = _empty_score(len(selected))
    wanted = selected[["source_id", "site_id", "origin_year_month"]].rename(
        columns={"origin_year_month": "year_month"}
    )
    joined = wanted.merge(
        states[["source_id", "site_id", "year_month", "yN", "yF", "yT"]],
        on=["source_id", "site_id", "year_month"], how="left", validate="many_to_one", sort=False,
    )
    score = _state_score(joined[["yN", "yF", "yT"]].to_numpy(dtype=np.float64))
    usable = valid & np.isfinite(score)
    result["valid"] = np.repeat(usable[:, None], 3, axis=1)
    result["bloom"] = np.repeat(np.where(usable, score, np.nan)[:, None], 3, axis=1)
    result["risk"] = result["bloom"].copy()
    result["threshold"][usable, :] = 0.5
    return result


def _score_cohort(
    cohort: str,
    bundle: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
    arrays: Mapping[str, np.ndarray],
    warmup: pd.DataFrame,
    specs: Mapping[tuple[str, int, int], Mapping[str, Any]],
    thresholds: Mapping[tuple[str, int, int], float],
    conformal: Mapping[tuple[str, int, int, str], float],
    *,
    root: Path,
) -> tuple[pd.DataFrame, dict[tuple[str, int], dict[str, np.ndarray]]]:
    intents, history, origins = bundle
    cohort_sites = set(intents["site_id"].astype(str))
    cohort_warmup = warmup.loc[warmup["site_id"].astype(str).isin(cohort_sites)].copy()
    monthly = phase3._deduplicated_month_surface(history, cohort_warmup)
    expert = _expert_states(monthly)
    adaptive = phase3._adaptive_states(arrays, monthly)
    p0_frame, p0_valid = _sequence_frame(intents, history, expert)
    ordered_origins = origins.sort_values(
        ["source_id", "site_id", "origin_year_month", "origin_id"], kind="stable"
    ).reset_index(drop=True)
    if not ordered_origins["origin_id"].astype(str).equals(p0_frame["origin_id"].astype(str)):
        raise EvaluationError("Origin-feature order does not match intent order")
    scores: dict[tuple[str, int], dict[str, np.ndarray]] = {}
    b2_predictions = phase3._load_b2_predictions(root, ordered_origins)
    for seed in EXPECTED_SEEDS:
        scores[("P0", seed)] = _temporal_scores(
            "P0", seed, p0_frame, p0_valid, specs, thresholds, conformal, root=root
        )
        p1_frame, p1_valid = _sequence_frame(intents, history, adaptive[seed])
        scores[("P1", seed)] = _temporal_scores(
            "P1", seed, p1_frame, p1_valid, specs, thresholds, conformal, root=root
        )
        phase_b2 = b2_predictions[("B2", seed)]
        b2 = _empty_score(len(p0_frame))
        b2["valid"] = phase_b2["valid"].astype(bool)
        b2["bloom"] = phase_b2["bloom_raw"].astype(np.float64)
        b2["risk"] = b2["bloom"].copy()
        b2["threshold"][b2["valid"]] = 0.5
        scores[("B2", seed)] = b2
        current = _current_state_scores(p1_frame, p1_valid, adaptive[seed])
        scores[("A1", seed)] = current
        scores[("B1", seed)] = {name: values.copy() for name, values in current.items()}
    scores[("A0", -1)] = _current_state_scores(p0_frame, p0_valid, expert)
    phase_m0 = phase3._load_m0_predictions(ordered_origins)[("M0", 1729)]
    m0 = _empty_score(len(p0_frame))
    m0["valid"] = phase_m0["valid"].astype(bool)
    m0["bloom"] = phase_m0["bloom_raw"].astype(np.float64)
    m0["risk"] = phase_m0["continuous"].astype(np.float64)
    m0["threshold"][m0["valid"]] = 0.5
    scores[("M0", -1)] = m0
    if cohort == "fresh_primary" and (len(p0_frame) != 2286 or not p0_valid.all()):
        raise EvaluationError("Fresh-primary temporal input eligibility drifted")
    return p0_frame, scores


def _family_scores(scores: dict[tuple[str, int], dict[str, np.ndarray]]) -> dict[tuple[str, int], dict[str, np.ndarray]]:
    result = dict(scores)
    for model_id in ("P0", "P1", "B2", "A1", "B1"):
        slots = [scores[(model_id, seed)] for seed in EXPECTED_SEEDS]
        family = _empty_score(slots[0]["valid"].shape[0])
        valid_stack = np.stack([slot["valid"] for slot in slots])
        family["valid"] = np.asarray(valid_stack.all(axis=0), dtype=bool)
        for name in ("bloom", "risk", "sigma", "lower", "upper", "threshold"):
            stack = np.stack([slot[name] for slot in slots])
            finite = np.isfinite(stack)
            value = np.divide(
                np.nansum(stack, axis=0),
                finite.sum(axis=0),
                out=np.full(stack.shape[1:], np.nan, dtype=np.float64),
                where=finite.sum(axis=0) > 0,
            )
            value[~family["valid"]] = np.nan
            family[name] = value
        result[(model_id, -1)] = family
    return result


def _target_month(origin: str, horizon: int) -> str:
    value = cast(pd.Period, pd.Period(str(origin), freq="M")) + horizon
    return str(value)


def _scan_targets(metadata: pd.DataFrame, *, root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    sites = sorted(metadata["site_id"].astype(str).unique())
    origins = metadata["origin_year_month"].astype(str)
    dataset = ds.dataset(_require_regular(root, TARGETS_PATH).as_posix(), format="parquet")
    columns = [
        "source_id", "site_id", "origin_year_month", "target_year_month",
        "horizon_months", "target_month_exists", "has_target",
        "future_chlorophyll_a_ugL", "bloom_h", "target_risk_chla_h",
        "target_trophic_state_h",
    ]
    predicate = (
        (ds.field("source_id") == "wqp")
        & ds.field("site_id").isin(sites)
        & (ds.field("origin_year_month") >= str(origins.min()))
        & (ds.field("origin_year_month") <= str(origins.max()))
        & ds.field("horizon_months").isin([1, 2, 3])
    )
    frame = dataset.scanner(columns=columns, filter=predicate).to_table().to_pandas()
    keys = ["source_id", "site_id", "origin_year_month", "horizon_months"]
    if frame.duplicated(keys).any() or not set(frame["site_id"].astype(str)).issubset(set(sites)):
        raise EvaluationError("Predicate-pushed evaluation targets crossed the key boundary")
    return frame, {
        "scanner": "pyarrow_dataset_predicate_pushdown",
        "projected_columns": columns,
        "rows_materialized": len(frame),
        "locations_materialized": int(frame["site_id"].nunique()),
        "origin_min": str(origins.min()),
        "origin_max": str(origins.max()),
        "replacement_used": False,
    }


def _prediction_rows(
    metadata: pd.DataFrame,
    scores: Mapping[tuple[str, int], Mapping[str, np.ndarray]],
    targets: pd.DataFrame,
) -> pd.DataFrame:
    key_rows: list[dict[str, Any]] = []
    for row in metadata.to_dict(orient="records"):
        for horizon in HORIZONS:
            key_rows.append({
                **{key: row[key] for key in (
                    "origin_id", "source_id", "site_id", "evaluation_cohort",
                    "origin_year_month", "base_input_status", "base_input_reason",
                )},
                "horizon_months": horizon,
                "target_year_month": _target_month(str(row["origin_year_month"]), horizon),
                "_origin_index": len(key_rows) // 3,
            })
    keys = pd.DataFrame(key_rows)
    joined = keys.merge(
        targets,
        on=["source_id", "site_id", "origin_year_month", "target_year_month", "horizon_months"],
        how="left", validate="one_to_one", sort=False,
    )
    target_available = (
        joined["has_target"].fillna(False).astype(bool)
        & pd.to_numeric(joined["future_chlorophyll_a_ugL"], errors="coerce").notna()
        & pd.to_numeric(joined["bloom_h"], errors="coerce").notna()
        & pd.to_numeric(joined["target_risk_chla_h"], errors="coerce").notna()
    )
    rows: list[pd.DataFrame] = []
    seeded_models = {"P0", "P1", "B2", "A1", "B1"}
    for (model_id, seed), score in sorted(scores.items()):
        aggregation = "family" if seed == -1 else "seed"
        if model_id not in seeded_models and seed != -1:
            raise EvaluationError("Deterministic comparator acquired a pseudo-seed")
        frame = joined.copy()
        origin_index = frame["_origin_index"].to_numpy(dtype=np.int64)
        horizon_index = frame["horizon_months"].to_numpy(dtype=np.int64) - 1
        valid = score["valid"][origin_index, horizon_index].astype(bool)
        for output, name in (
            ("bloom_probability", "bloom"), ("alert_threshold", "threshold"),
            ("predicted_risk_chla", "risk"), ("predicted_risk_sigma", "sigma"),
            ("risk_interval_lower_90", "lower"), ("risk_interval_upper_90", "upper"),
        ):
            values = score[name][origin_index, horizon_index]
            frame[output] = np.where(valid, values, np.nan)
        frame["model_id"] = model_id
        frame["base_seed"] = seed
        frame["aggregation_level"] = aggregation
        frame["intent_to_predict"] = True
        frame["input_eligible"] = frame["base_input_status"].astype(str).eq("eligible")
        frame["prediction_status"] = np.where(valid, "success", "failed")
        frame["failure_reason"] = np.where(
            valid, "", np.where(frame["input_eligible"], "model_prediction_unavailable", frame["base_input_reason"])
        )
        frame["prediction_successful"] = valid
        frame["target_month_exists"] = frame["target_month_exists"].fillna(False).astype(bool)
        frame["target_available"] = target_available.to_numpy()
        frame["metric_evaluable"] = valid & target_available.to_numpy()
        frame["predicted_alert"] = np.where(
            valid,
            frame["bloom_probability"].to_numpy(dtype=np.float64) >= frame["alert_threshold"].to_numpy(dtype=np.float64),
            False,
        )
        for cutoff in SENSITIVITY_CUTOFFS:
            label = f"outcome_bloom_{int(cutoff)}"
            frame[label] = np.where(
                target_available.to_numpy(),
                pd.to_numeric(frame["future_chlorophyll_a_ugL"], errors="coerce").to_numpy(dtype=np.float64) >= cutoff,
                False,
            )
        frame["result_state"] = np.where(
            frame["metric_evaluable"],
            np.where(frame["evaluation_cohort"].eq("fresh_primary"), "confirmatory_available", "posthoc_available"),
            np.where(frame["prediction_successful"], "insufficient_support", "failed"),
        )
        rows.append(frame)
    output = pd.concat(rows, ignore_index=True)
    family = output.loc[
        output["aggregation_level"].eq("family") & output["model_id"].isin(PRIMARY_MODELS),
        ["evaluation_cohort", "source_id", "site_id", "origin_year_month", "horizon_months", "model_id", "prediction_successful"],
    ]
    common = family.pivot(
        index=["evaluation_cohort", "source_id", "site_id", "origin_year_month", "horizon_months"],
        columns="model_id", values="prediction_successful",
    ).reset_index()
    common["shared_success"] = common[list(PRIMARY_MODELS)].all(axis=1)
    output = output.merge(
        common.drop(columns=list(PRIMARY_MODELS)),
        on=["evaluation_cohort", "source_id", "site_id", "origin_year_month", "horizon_months"],
        how="left", validate="many_to_one", sort=False,
    )
    output["shared_success"] = output["shared_success"].fillna(False) & output["target_available"]
    output = output.sort_values(
        ["evaluation_cohort", "model_id", "aggregation_level", "base_seed", "source_id", "site_id", "origin_year_month", "horizon_months"],
        kind="stable",
    ).reset_index(drop=True)
    if output.duplicated([
        "evaluation_cohort", "model_id", "base_seed", "aggregation_level",
        "source_id", "site_id", "origin_year_month", "horizon_months",
    ]).any():
        raise EvaluationError("Prediction identities are duplicated")
    return output.loc[:, list(PREDICTION_COLUMNS)]


def _weights(frame: pd.DataFrame, estimand: str) -> np.ndarray:
    if estimand == "observation_weighted":
        return np.ones(len(frame), dtype=np.float64)
    counts = frame.groupby(["source_id", "site_id"], sort=False)["origin_id"].transform("size")
    return 1.0 / counts.to_numpy(dtype=np.float64)


def _ece(y: np.ndarray, p: np.ndarray, w: np.ndarray) -> float:
    bins = np.minimum((p * 10).astype(int), 9)
    total = float(w.sum())
    value = 0.0
    for index in range(10):
        mask = bins == index
        if mask.any():
            value += float(w[mask].sum() / total) * abs(
                float(np.average(p[mask], weights=w[mask])) - float(np.average(y[mask], weights=w[mask]))
            )
    return value


def _metric_rows(predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    groups = ["evaluation_cohort", "model_id", "base_seed", "aggregation_level", "horizon_months"]
    for keys, group in predictions.groupby(groups, sort=True, dropna=False):
        cohort, model_id, seed, aggregation, horizon = cast(tuple[Any, ...], keys)
        evaluable = group.loc[group["metric_evaluable"]].copy()
        for estimand in ("observation_weighted", "site_weighted"):
            base = {
                "evaluation_cohort": cohort, "model_id": model_id, "base_seed": seed,
                "aggregation_level": aggregation, "horizon_months": horizon,
                "estimand": estimand, "endpoint": "bloom_30_ugL",
                "attempted": len(group), "input_eligible": int(group["input_eligible"].sum()),
                "prediction_successful": int(group["prediction_successful"].sum()),
                "target_available": int(group["target_available"].sum()),
                "metric_evaluable": len(evaluable), "shared_success": int(group["shared_success"].sum()),
            }
            if evaluable.empty:
                for metric in ("brier", "pr_auc", "ece10", "reliability_bias", "f2", "recall", "precision", "macro_f1", "risk_mae", "risk_rmse", "risk_nll"):
                    rows.append({**base, "metric": metric, "estimate": np.nan, "status": "not_estimable"})
                continue
            weights = _weights(evaluable, estimand)
            y = evaluable["outcome_bloom_30"].astype(int).to_numpy()
            p = evaluable["bloom_probability"].to_numpy(dtype=np.float64)
            predicted = evaluable["predicted_alert"].astype(int).to_numpy()
            tp = float(weights[(predicted == 1) & (y == 1)].sum())
            fp = float(weights[(predicted == 1) & (y == 0)].sum())
            fn = float(weights[(predicted == 0) & (y == 1)].sum())
            f2 = 5.0 * tp / (5.0 * tp + 4.0 * fn + fp) if 5.0 * tp + 4.0 * fn + fp else np.nan
            probability_metrics = {
                "brier": float(np.average((p - y) ** 2, weights=weights)),
                "pr_auc": float(average_precision_score(y, p, sample_weight=weights)) if len(np.unique(y)) == 2 else np.nan,
                "ece10": _ece(y, p, weights),
                "reliability_bias": float(np.average(p - y, weights=weights)),
                "f2": f2,
                "recall": float(recall_score(y, predicted, sample_weight=weights, zero_division=0)),
                "precision": float(precision_score(y, predicted, sample_weight=weights, zero_division=0)),
                "macro_f1": float(f1_score(y, predicted, average="macro", sample_weight=weights, zero_division=0)),
            }
            target_risk = evaluable["target_risk_chla_h"].to_numpy(dtype=np.float64)
            predicted_risk = evaluable["predicted_risk_chla"].to_numpy(dtype=np.float64)
            finite_risk = np.isfinite(target_risk) & np.isfinite(predicted_risk)
            if finite_risk.any():
                risk_w = weights[finite_risk]
                residual = predicted_risk[finite_risk] - target_risk[finite_risk]
                probability_metrics["risk_mae"] = float(np.average(np.abs(residual), weights=risk_w))
                probability_metrics["risk_rmse"] = float(np.sqrt(np.average(residual**2, weights=risk_w)))
            else:
                probability_metrics["risk_mae"] = np.nan
                probability_metrics["risk_rmse"] = np.nan
            sigma = evaluable["predicted_risk_sigma"].to_numpy(dtype=np.float64)
            finite_nll = finite_risk & np.isfinite(sigma) & (sigma > 0.0)
            if finite_nll.any():
                residual = predicted_risk[finite_nll] - target_risk[finite_nll]
                variance = sigma[finite_nll] ** 2
                probability_metrics["risk_nll"] = float(np.average(
                    0.5 * (np.log(2.0 * np.pi * variance) + residual**2 / variance),
                    weights=weights[finite_nll],
                ))
            else:
                probability_metrics["risk_nll"] = np.nan
            for metric, estimate in probability_metrics.items():
                rows.append({
                    **base, "metric": metric, "estimate": estimate,
                    "status": "estimated" if math.isfinite(float(estimate)) else "not_estimable",
                })
    return pd.DataFrame(rows)


def _availability(predictions: pd.DataFrame) -> pd.DataFrame:
    groups = ["evaluation_cohort", "model_id", "base_seed", "aggregation_level", "horizon_months"]
    rows = []
    for raw_keys, group in predictions.groupby(groups, sort=True, dropna=False):
        keys = cast(tuple[Any, ...], raw_keys)
        attempted = len(group)
        rows.append(dict(zip(groups, keys, strict=True)) | {
            "attempted": attempted,
            "input_eligible": int(group["input_eligible"].sum()),
            "prediction_successful": int(group["prediction_successful"].sum()),
            "target_available": int(group["target_available"].sum()),
            "metric_evaluable": int(group["metric_evaluable"].sum()),
            "shared_success": int(group["shared_success"].sum()),
            "success_rate": float(group["prediction_successful"].mean()),
            "evaluable_rate": float(group["metric_evaluable"].mean()),
            "abstention_rate": float((~group["prediction_successful"]).mean()),
            "failure_rate": float(group["prediction_status"].eq("failed").mean()),
        })
    return pd.DataFrame(rows)


def _funnel(predictions: pd.DataFrame) -> pd.DataFrame:
    return _availability(predictions)[[
        "evaluation_cohort", "model_id", "base_seed", "aggregation_level", "horizon_months",
        "attempted", "input_eligible", "prediction_successful", "target_available",
        "metric_evaluable", "shared_success",
    ]]


def _pairwise(predictions: pd.DataFrame) -> pd.DataFrame:
    family = predictions.loc[predictions["aggregation_level"].eq("family")]
    rows = []
    for cohort in sorted(family["evaluation_cohort"].unique()):
        for horizon in HORIZONS:
            part = family.loc[family["evaluation_cohort"].eq(cohort) & family["horizon_months"].eq(horizon)]
            for comparison, challenger, reference, tier in COMPARISONS:
                left = part.loc[part["model_id"].eq(challenger), ["origin_id", "metric_evaluable"]]
                right = part.loc[part["model_id"].eq(reference), ["origin_id", "metric_evaluable"]]
                joined = left.merge(right, on="origin_id", how="outer", suffixes=("_challenger", "_reference"), validate="one_to_one")
                rows.append({
                    "evaluation_cohort": cohort, "horizon_months": horizon,
                    "comparison_id": comparison, "comparison_tier": tier,
                    "challenger": challenger, "reference": reference,
                    "challenger_evaluable": int(joined["metric_evaluable_challenger"].fillna(False).sum()),
                    "reference_evaluable": int(joined["metric_evaluable_reference"].fillna(False).sum()),
                    "pairwise_common_rows": int((joined["metric_evaluable_challenger"].fillna(False) & joined["metric_evaluable_reference"].fillna(False)).sum()),
                    "inference_performed": False,
                })
    return pd.DataFrame(rows)


def _sensitivity(predictions: pd.DataFrame) -> pd.DataFrame:
    family = predictions.loc[predictions["aggregation_level"].eq("family")]
    rows = []
    for keys, group in family.groupby(["evaluation_cohort", "model_id", "horizon_months"], sort=True):
        cohort, model_id, horizon = keys
        evaluable = group.loc[group["metric_evaluable"]]
        for cutoff in SENSITIVITY_CUTOFFS:
            if evaluable.empty:
                metrics = {"brier": np.nan, "f2": np.nan, "recall": np.nan, "precision": np.nan, "macro_f1": np.nan}
            else:
                y = evaluable[f"outcome_bloom_{int(cutoff)}"].astype(int).to_numpy()
                p = evaluable["bloom_probability"].to_numpy(dtype=np.float64)
                pred = evaluable["predicted_alert"].astype(int).to_numpy()
                tp = int(((pred == 1) & (y == 1)).sum()); fp = int(((pred == 1) & (y == 0)).sum()); fn = int(((pred == 0) & (y == 1)).sum())
                metrics = {
                    "brier": float(np.mean((p - y) ** 2)),
                    "f2": 5.0 * tp / (5.0 * tp + 4.0 * fn + fp) if 5 * tp + 4 * fn + fp else np.nan,
                    "recall": float(recall_score(y, pred, zero_division=0)),
                    "precision": float(precision_score(y, pred, zero_division=0)),
                    "macro_f1": float(f1_score(y, pred, average="macro", zero_division=0)),
                }
            for metric, estimate in metrics.items():
                rows.append({
                    "evaluation_cohort": cohort, "model_id": model_id, "horizon_months": horizon,
                    "chlorophyll_cutoff_ugL": cutoff, "primary_endpoint": cutoff == 30.0,
                    "metric": metric, "estimate": estimate,
                    "rows": len(evaluable),
                    "interpretation": "primary_calibrated_endpoint" if cutoff == 30.0 else "predeclared_endpoint_sensitivity_without_recalibration",
                    "inference_performed": False,
                })
    return pd.DataFrame(rows)


def _uncertainty(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    groups = ["evaluation_cohort", "model_id", "base_seed", "aggregation_level", "horizon_months"]
    for raw_keys, group in predictions.groupby(groups, sort=True, dropna=False):
        keys = cast(tuple[Any, ...], raw_keys)
        usable = group.loc[
            group["metric_evaluable"]
            & group["risk_interval_lower_90"].notna()
            & group["risk_interval_upper_90"].notna()
        ]
        if usable.empty:
            picp = mpiw = winkler = np.nan
            status = "not_applicable"
        else:
            y = usable["target_risk_chla_h"].to_numpy(dtype=np.float64)
            lower = usable["risk_interval_lower_90"].to_numpy(dtype=np.float64)
            upper = usable["risk_interval_upper_90"].to_numpy(dtype=np.float64)
            width = upper - lower
            penalty = np.where(y < lower, 20.0 * (lower - y), np.where(y > upper, 20.0 * (y - upper), 0.0))
            picp = float(np.mean((y >= lower) & (y <= upper)))
            mpiw = float(np.mean(width))
            winkler = float(np.mean(width + penalty))
            status = "descriptive_available"
        rows.append(dict(zip(groups, keys, strict=True)) | {
            "coverage_nominal": 0.90, "rows": len(usable), "picp": picp,
            "mpiw": mpiw, "winkler": winkler, "status": status,
            "interval_method": "locked_statewise_split_conformal_propagated_to_irc",
            "inference_performed": False,
        })
    return pd.DataFrame(rows)


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, lineterminator="\n").encode("utf-8")


def _parquet_bytes(frame: pd.DataFrame) -> bytes:
    table = pa.Table.from_pandas(frame, preserve_index=False)
    buffer = io.BytesIO()
    pq.write_table(
        table, buffer, compression="zstd", use_dictionary=False,
        write_statistics=True, data_page_version="1.0",
    )
    return buffer.getvalue()


def _report_bytes(predictions: pd.DataFrame, metrics: pd.DataFrame, availability: pd.DataFrame) -> bytes:
    family = metrics.loc[metrics["aggregation_level"].eq("family") & metrics["metric"].isin(["brier", "pr_auc"])]
    lines = [
        "# Closure V2 sealed benchmark", "",
        "P13 evaluated the frozen P0/P1 temporal families without refit, recalibration, threshold changes, replacement, or statistical inference.", "",
        "## Cohorts", "",
    ]
    for cohort in ("legacy_posthoc", "fresh_primary"):
        part = predictions.loc[predictions["evaluation_cohort"].eq(cohort)]
        lines.append(f"- `{cohort}`: {part['origin_id'].nunique():,} intent origins across {part['site_id'].nunique():,} locations.")
    lines.extend([
        "", "`legacy_posthoc` is retrospective/complementary. `fresh_primary` supports at most internal evaluation on unused WQP monitoring locations; it is not external validation.", "",
        "## Family metrics", "",
        family.to_markdown(index=False), "",
        "## Availability", "",
        availability.loc[availability["aggregation_level"].eq("family")].to_markdown(index=False), "",
        "## Interpretation boundaries", "",
        "The five seeds are averaged as one family estimator and are not ecological replicates. A1 and B1 share the same no-current-Chl-a persistence score for the bloom endpoint and are retained under their separately registered roles. Sensitivity cutoffs 25/33/50 reuse frozen probabilities and thresholds without recalibration. P13 contains no p-values, confidence intervals for model contrasts, winner declaration, field-causal claim, or official recommendation.", "",
    ])
    return "\n".join(lines).encode("utf-8")


def _build_payloads(
    predictions: pd.DataFrame,
) -> tuple[dict[Path, bytes], dict[str, pd.DataFrame]]:
    metrics = _metric_rows(predictions)
    availability = _availability(predictions)
    tables = {
        "metrics": metrics,
        "availability": availability,
        "funnel": _funnel(predictions),
        "pairwise": _pairwise(predictions),
        "sensitivity": _sensitivity(predictions),
        "uncertainty": _uncertainty(predictions),
    }
    payloads = {
        PREDICTIONS_PATH: _parquet_bytes(predictions),
        METRICS_PATH: _csv_bytes(tables["metrics"]),
        AVAILABILITY_PATH: _csv_bytes(tables["availability"]),
        FUNNEL_PATH: _csv_bytes(tables["funnel"]),
        PAIRWISE_PATH: _csv_bytes(tables["pairwise"]),
        SENSITIVITY_PATH: _csv_bytes(tables["sensitivity"]),
        UNCERTAINTY_PATH: _csv_bytes(tables["uncertainty"]),
        REPORT_PATH: _report_bytes(predictions, metrics, availability),
    }
    return payloads, tables


def _exclusive_bundle(contents: Sequence[tuple[Path, bytes]], *, root: Path) -> None:
    created: list[tuple[Path, int]] = []
    temporary_paths: list[Path] = []
    try:
        for relative, content in contents:
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() or destination.is_symlink():
                raise EvaluationError(f"Refusing to overwrite P13 output: {relative}")
            temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
            temporary_paths.append(temporary)
            with temporary.open("xb") as handle:
                handle.write(content); handle.flush(); os.fsync(handle.fileno())
            os.link(temporary, destination)
            created.append((destination, destination.stat().st_ino))
            temporary.unlink()
    except BaseException:
        for destination, inode in reversed(created):
            if destination.is_file() and not destination.is_symlink() and destination.stat().st_ino == inode:
                destination.unlink()
        raise
    finally:
        for temporary in temporary_paths:
            temporary.unlink(missing_ok=True)


def _append_event(root: Path, event: Mapping[str, Any], *, expected_count: int) -> None:
    path = _require_regular(root, OUTCOME_LOG)
    flags = os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        events = _parse_log(path)
        if len(events) != expected_count:
            raise EvaluationError("Outcome access log changed before append")
        payload = _canonical_line(event)
        if os.write(descriptor, payload) != len(payload):
            raise EvaluationError("Short append to outcome access log")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _execution_id(authority: Mapping[str, Any], *, root: Path) -> str:
    payload = {
        "activation_id": cast(Mapping[str, Any], authority["activation"])["activation_id"],
        "head": authority["head"],
        "model_lock_sha256": cast(Mapping[str, Any], authority["model_lock"])["sha256"],
        "input_manifest_sha256": cast(Mapping[str, Any], authority["fresh_primary"])["manifest_sha256"],
        "evaluator_sha256": sha256_file(root / SCRIPT_PATH),
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def preflight(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    authority = validate_authority(root)
    cohorts = _load_cohorts(root)
    arrays, warmup, _, _ = phase3._load_overlay(root)
    specs, thresholds, conformal = _load_calibration(root)
    summaries = {}
    for cohort, bundle in cohorts.items():
        metadata, scores = _score_cohort(
            cohort, bundle, arrays, warmup, specs, thresholds, conformal, root=root
        )
        family = _family_scores(scores)
        summaries[cohort] = {
            "intent_origins": len(metadata),
            "locations": int(metadata["site_id"].nunique()),
            "registered_score_slots": len(family),
            "P0_family_success_rows_all_horizons": int(family[("P0", -1)]["valid"].sum()),
            "P1_family_success_rows_all_horizons": int(family[("P1", -1)]["valid"].sum()),
        }
    return {
        **authority,
        "status": "ready_to_consume_one_shot_evaluation",
        "cohorts": summaries,
        "execution_id": _execution_id(authority, root=root),
        "outputs_absent": all(not (root / path).exists() and not (root / path).is_symlink() for path in ALL_FINAL_PATHS),
        "writes_performed": False,
        "outcomes_opened": False,
    }


def execute(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    authority = validate_authority(root)
    if any((root / path).exists() or (root / path).is_symlink() for path in ALL_FINAL_PATHS):
        raise EvaluationError("P13 output namespace is not empty")
    guard = root / "tmp/closure_v2_evaluation.guard"
    guard.parent.mkdir(parents=True, exist_ok=True)
    try:
        guard.mkdir()
    except FileExistsError as error:
        raise EvaluationError("P13 evaluation guard already exists") from error
    execution_id = _execution_id(authority, root=root)
    activation = cast(Mapping[str, Any], authority["activation"])
    started = {
        "schema_version": "closure_v2_outcome_access_event_v1",
        "experiment_id": "closure_v2", "event_index": 1,
        "event_type": "evaluation_execution_started", "activation_id": activation["activation_id"],
        "execution_id": execution_id, "evaluation_cohorts": ["legacy_posthoc", "fresh_primary"],
        "outcome_access_authorized": True, "outcome_values_opened": False,
        "target_availability_inspected": False, "refit_performed": False,
        "recalibration_performed": False, "replacement_used": False,
    }
    _append_event(root, started, expected_count=1)
    try:
        cohorts = _load_cohorts(root)
        arrays, warmup, _, _ = phase3._load_overlay(root)
        specs, thresholds, conformal = _load_calibration(root)
        metadata_by_cohort: dict[str, pd.DataFrame] = {}
        score_by_cohort: dict[str, dict[tuple[str, int], dict[str, np.ndarray]]] = {}
        for cohort, bundle in cohorts.items():
            metadata, scores = _score_cohort(
                cohort, bundle, arrays, warmup, specs, thresholds, conformal, root=root
            )
            metadata_by_cohort[cohort] = metadata
            score_by_cohort[cohort] = _family_scores(scores)
        all_metadata = pd.concat(metadata_by_cohort.values(), ignore_index=True)
        targets, target_scan = _scan_targets(all_metadata, root=root)
        constructed = []
        for cohort in ("legacy_posthoc", "fresh_primary"):
            cohort_targets = targets.loc[
                targets["site_id"].astype(str).isin(set(metadata_by_cohort[cohort]["site_id"].astype(str)))
            ].copy()
            constructed.append(_prediction_rows(metadata_by_cohort[cohort], score_by_cohort[cohort], cohort_targets))
        predictions = pd.concat(constructed, ignore_index=True).sort_values(
            ["evaluation_cohort", "model_id", "aggregation_level", "base_seed", "source_id", "site_id", "origin_year_month", "horizon_months"],
            kind="stable",
        ).reset_index(drop=True)
        payloads, tables = _build_payloads(predictions)
        repeated_payloads, _ = _build_payloads(predictions.copy(deep=True))
        if {path: hashlib.sha256(value).hexdigest() for path, value in payloads.items()} != {
            path: hashlib.sha256(value).hexdigest() for path, value in repeated_payloads.items()
        }:
            raise EvaluationError("Temporary-output reproducibility check failed")
        _exclusive_bundle([(path, payloads[path]) for path in (PREDICTIONS_PATH, *LIGHT_PATHS)], root=root)
        completed = {
            "schema_version": "closure_v2_outcome_access_event_v1",
            "experiment_id": "closure_v2", "event_index": 2,
            "event_type": "evaluation_execution_completed", "activation_id": activation["activation_id"],
            "execution_id": execution_id, "outcome_values_opened": True,
            "target_availability_inspected": True, "benchmark_executed": True,
            "refit_performed": False, "recalibration_performed": False,
            "replacement_used": False, "predictions_rows": len(predictions),
            "target_scan": target_scan,
            "physical_prediction_sha256": sha256_file(root / PREDICTIONS_PATH),
            "manifest_pending_dvc_finalize": True,
        }
        _append_event(root, completed, expected_count=2)
        return {
            "status": "evaluation_bundle_written_unfinalized",
            "execution_id": execution_id, "predictions_rows": len(predictions),
            "intent_origins": int(predictions["origin_id"].nunique()),
            "cohorts": predictions.groupby("evaluation_cohort")["origin_id"].nunique().to_dict(),
            "metric_rows": len(tables["metrics"]), "outcomes_opened": True,
            "refit_performed": False, "recalibration_performed": False,
            "next_required": ".venv/bin/dvc add data/closure_v2/predictions_long.parquet then --finalize",
        }
    finally:
        guard.rmdir()


def repair_failed_values(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Repair the uncommitted P13 representation without reopening outcomes.

    The first local bundle retained B2 probabilities on rows whose sealed
    validity mask said ``failed``.  This repair only nulls prediction fields on
    failed rows and rebuilds derivative tables from the already materialized
    prediction table.  It never reads TARGETS_PATH or invokes any model.
    """
    events = _parse_log(_require_regular(root, OUTCOME_LOG))
    if [event.get("event_type") for event in events] != [
        "evaluation_activation", "evaluation_execution_started", "evaluation_execution_completed"
    ]:
        raise EvaluationError("Outcome log is not in the exact pre-repair state")
    for path in (PREDICTIONS_PATH, PREDICTIONS_POINTER, *LIGHT_PATHS, MANIFEST_PATH):
        _require_regular(root, path)
    predictions = pq.read_table(root / PREDICTIONS_PATH).to_pandas()
    failed = ~predictions["prediction_successful"].astype(bool)
    prediction_fields = [
        "bloom_probability", "alert_threshold", "predicted_risk_chla",
        "predicted_risk_sigma", "risk_interval_lower_90", "risk_interval_upper_90",
    ]
    leaked = failed & predictions[prediction_fields].notna().any(axis=1)
    if int(leaked.sum()) != 47_700 or set(predictions.loc[leaked, "model_id"].astype(str)) != {"B2"}:
        raise EvaluationError("The local failed-value defect does not match the audited scope")
    corrected = predictions.copy(deep=True)
    corrected.loc[failed, prediction_fields] = np.nan
    if corrected.loc[failed, prediction_fields].notna().any().any():
        raise EvaluationError("Failed prediction values were not fully nulled")
    payloads, _ = _build_payloads(corrected)
    repeated, _ = _build_payloads(corrected.copy(deep=True))
    if {key: hashlib.sha256(value).hexdigest() for key, value in payloads.items()} != {
        key: hashlib.sha256(value).hexdigest() for key, value in repeated.items()
    }:
        raise EvaluationError("Corrected temporary outputs are not reproducible")
    execution_id = str(events[1]["execution_id"])
    archive_root = root / "tmp" / f"p13_failed_value_bundle_{execution_id}"
    if archive_root.exists() or archive_root.is_symlink():
        raise EvaluationError("P13 failed-value archive already exists")
    archived: list[tuple[Path, Path, int]] = []
    try:
        for relative in (PREDICTIONS_PATH, PREDICTIONS_POINTER, *LIGHT_PATHS, MANIFEST_PATH):
            source = root / relative
            destination = archive_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            inode = source.stat().st_ino
            os.link(source, destination)
            archived.append((source, destination, inode))
        for source, _, inode in archived:
            if source.is_symlink() or not source.is_file() or source.stat().st_ino != inode:
                raise EvaluationError("P13 output changed during recoverable archival")
            source.unlink()
        _exclusive_bundle([(path, payloads[path]) for path in (PREDICTIONS_PATH, *LIGHT_PATHS)], root=root)
        correction = {
            "schema_version": "closure_v2_outcome_access_event_v1",
            "experiment_id": "closure_v2", "event_index": 3,
            "event_type": "evaluation_bundle_corrected",
            "activation_id": events[0]["activation_id"], "execution_id": execution_id,
            "correction_scope": "null_failed_B2_prediction_values_only",
            "rows_corrected": int(leaked.sum()), "models_reexecuted": False,
            "outcomes_reopened": False, "target_availability_reinspected": False,
            "refit_performed": False, "recalibration_performed": False,
            "replacement_used": False,
            "archived_local_bundle": archive_root.relative_to(root).as_posix(),
            "physical_prediction_sha256": sha256_file(root / PREDICTIONS_PATH),
            "manifest_pending_dvc_finalize": True,
        }
        _append_event(root, correction, expected_count=3)
    except BaseException:
        # The archived hardlinks remain the recoverable authority if publication
        # of the corrected canonical names cannot be completed.
        raise
    return {
        "status": "evaluation_bundle_corrected_unfinalized",
        "execution_id": execution_id, "rows_corrected": int(leaked.sum()),
        "models_reexecuted": False, "outcomes_reopened": False,
        "archive": archive_root.relative_to(root).as_posix(),
        "next_required": ".venv/bin/dvc add data/closure_v2/predictions_long.parquet then --finalize",
    }


def finalize(*, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    if (root / MANIFEST_PATH).exists() or (root / MANIFEST_PATH).is_symlink():
        raise EvaluationError("Evaluation manifest already exists")
    for path in (PREDICTIONS_PATH, PREDICTIONS_POINTER, *LIGHT_PATHS):
        _require_regular(root, path)
    events = _parse_log(_require_regular(root, OUTCOME_LOG))
    event_types = [event.get("event_type") for event in events]
    if event_types not in (
        ["evaluation_activation", "evaluation_execution_started", "evaluation_execution_completed"],
        ["evaluation_activation", "evaluation_execution_started", "evaluation_execution_completed", "evaluation_bundle_corrected"],
    ):
        raise EvaluationError("Outcome access log is not ready for finalization")
    pointer = yaml.safe_load((root / PREDICTIONS_POINTER).read_text(encoding="utf-8"))
    outs = pointer.get("outs") if isinstance(pointer, Mapping) else None
    if not isinstance(outs, list) or len(outs) != 1 or not isinstance(outs[0], Mapping):
        raise EvaluationError("Prediction DVC pointer is malformed")
    record = outs[0]
    physical = root / PREDICTIONS_PATH
    if (
        record.get("path") != PREDICTIONS_PATH.name
        or record.get("size") != physical.stat().st_size
        or record.get("md5") != md5_file(physical)
    ):
        raise EvaluationError("Prediction DVC pointer does not bind the physical table")
    predictions = pq.read_table(physical).to_pandas()
    if tuple(predictions.columns) != PREDICTION_COLUMNS:
        raise EvaluationError("Final prediction table columns drifted")
    expected_attempts = {"legacy_posthoc": 4488, "fresh_primary": 2286}
    if predictions.groupby("evaluation_cohort")["origin_id"].nunique().to_dict() != expected_attempts:
        raise EvaluationError("Final intent-origin denominators drifted")
    manifest = {
        "schema_version": "closure_v2_evaluation_manifest_v1",
        "experiment_id": "closure_v2", "phase": "P13",
        "status": "completed", "execution_id": events[1]["execution_id"],
        "activation_id": events[0]["activation_id"],
        "model_lock_tag": MODEL_LOCK_TAG,
        "model_lock_sha256": sha256_file(root / MODEL_LOCK_PATH),
        "evaluation_cohorts": expected_attempts,
        "prediction_rows": len(predictions),
        "prediction_columns": list(PREDICTION_COLUMNS),
        "primary_endpoint_chlorophyll_cutoff_ugL": 30,
        "sensitivity_cutoffs_ugL": [25, 30, 33, 50],
        "estimands": ["observation_weighted", "site_weighted"],
        "family_prediction": "mean_probability_over_available_registered_seeds",
        "seed_pseudoreplication": False,
        "inference_performed": False,
        "refit_performed": False, "recalibration_performed": False,
        "threshold_changed": False, "replacement_used": False,
        "legacy_and_fresh_pooled": False,
        "reproducibility_check": "two_identical_in_memory_output_serializations_passed",
        "failed_prediction_values_nulled": bool(len(events) == 4),
        "post_execution_correction": None if len(events) == 3 else events[3]["correction_scope"],
        "models_reexecuted_for_correction": False,
        "outcomes_reopened_for_correction": False,
        "outcome_access_events": len(events),
        "inputs": [
            file_record(root / path, root=root, role="sealed_evaluation_input")
            for path in (SCRIPT_PATH, MODEL_LOCK_PATH, INPUT_MANIFEST, CALIBRATOR_PATH, THRESHOLD_PATH, CONFORMAL_PATH, OUTCOME_LOG)
        ],
        "data_artifact": {
            **file_record(physical, root=root, role="predictions_long"),
            "dvc_pointer": PREDICTIONS_POINTER.as_posix(),
            "dvc_md5": record["md5"], "dvc_size": record["size"],
        },
        "outputs": [file_record(root / path, root=root, role="evaluation_output") for path in (PREDICTIONS_POINTER, *LIGHT_PATHS)],
        "manifest_written_last": True,
    }
    _exclusive_bundle([(MANIFEST_PATH, canonical_json_bytes(manifest))], root=root)
    return {
        "status": "evaluation_completed", "execution_id": manifest["execution_id"],
        "prediction_rows": len(predictions), "manifest_sha256": sha256_file(root / MANIFEST_PATH),
        "refit_performed": False, "recalibration_performed": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--execute", action="store_true")
    group.add_argument("--finalize", action="store_true")
    group.add_argument("--repair-failed-values", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = (
        execute() if args.execute
        else repair_failed_values() if args.repair_failed_values
        else finalize() if args.finalize
        else preflight()
    )
    print(canonical_json_bytes(result).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
