"""Pure Closure V1 E3 bloom-threshold sensitivity component.

E3 receives the locked, already-opened prediction surface from the sealed
batch runner.  It never opens a path and never writes an artifact.  Temporal
model scores are held fixed; for each predeclared Chl-a threshold, an
independent Platt calibrator and decision threshold are fitted on validation
rows only, then applied without refitting to the legacy-test and location-
holdout rows.  Degenerate or unavailable model slots remain explicit instead
of being replaced with synthetic predictions.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    fbeta_score,
    precision_score,
    recall_score,
)


COMPONENT_ID = "E3_threshold_sensitivity"
STAGE_ID = "E3"
GATE = "E0-U"
RNG_SEED = 1729
THRESHOLDS_UG_L = (25.0, 30.0, 33.0, 50.0)
PRIMARY_THRESHOLD_UG_L = 30.0
HORIZONS = (1, 2, 3)
EVALUATION_COHORTS = ("legacy_development", "location_holdout")
VALIDATION_ROLE = "validation"
TEST_ROLE = "test"
MODEL_PAIRS = (
    ("P1", "B1"),
    ("P1", "B2"),
    ("P1", "P0"),
    ("P1", "M0"),
    ("F1", "F0"),
    ("A2", "P1"),
)
SOFTWARE_EVIDENCE_KEYS = frozenset(
    {
        "public_tests_xml",
        "test_report",
        "openapi",
        "openapi_contract_report",
        "end_to_end_report",
        "environment",
    }
)
CONTEXT_KEYS = frozenset(
    {
        "execution_id",
        "rng_seed",
        "tables",
        "stage_results",
        "model_availability",
        "software_evidence",
    }
)
PREDICTION_KEY_COLUMNS = (
    "source_id",
    "site_id",
    "common_origin_id",
    "horizon_months",
    "model_id",
    "model_seed",
    "seed_slot",
)
PREDICTION_REQUIRED_COLUMNS = (
    *PREDICTION_KEY_COLUMNS,
    "evaluation_cohort",
    "evaluation_role",
    "terminal_status",
    "continuous_score",
    "actual_value",
)
OUTPUT_PATHS = (
    "reports/closure_v1/03_thresholds/threshold_prevalence.csv",
    "reports/closure_v1/03_thresholds/threshold_metrics.csv",
    "reports/closure_v1/03_thresholds/threshold_pairwise_differences.csv",
    "reports/closure_v1/03_thresholds/rank_stability.csv",
    "reports/closure_v1/03_thresholds/threshold_sensitivity_report.md",
)
OUTPUT_TABLES = (
    "e3_threshold_prevalence",
    "e3_threshold_metrics",
    "e3_threshold_pairwise",
    "e3_rank_stability",
)
REQUIRED_NONEMPTY_TABLES = (
    "e3_threshold_prevalence",
    "e3_threshold_metrics",
    "e3_threshold_pairwise",
)


class ClosureThresholdSensitivityError(RuntimeError):
    """Raised when the E3 in-memory contract drifts."""


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _contract_sha256(contract: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(dict(contract))).hexdigest()


def _require_authority(authority: Mapping[str, Any]) -> None:
    required = {
        "gate": GATE,
        "effective_authority": True,
        "sealed_batch_execution_authorized": True,
        "e0_m_authorized": True,
        "e0_u_authorized": True,
        "evaluation_authorized": True,
        "outcome_access_authorized": True,
        "writes_performed": False,
    }
    if not isinstance(authority, Mapping):
        raise ClosureThresholdSensitivityError("E3 authority is not a mapping")
    for key, expected in required.items():
        if type(authority.get(key)) is not type(expected) or authority.get(key) != expected:
            raise ClosureThresholdSensitivityError(f"E3 authority field drifted: {key}")


def _require_component_contract(contract: Mapping[str, Any]) -> None:
    if not isinstance(contract, Mapping):
        raise ClosureThresholdSensitivityError("E3 sealed contract is not a mapping")
    if contract.get("formal_model_lock_gate") != "E0-M" or contract.get(
        "execution_gate"
    ) != GATE:
        raise ClosureThresholdSensitivityError("E3 sealed gate contract drifted")
    components = contract.get("components")
    if not isinstance(components, Sequence) or isinstance(components, (str, bytes)):
        raise ClosureThresholdSensitivityError("E3 component registry is malformed")
    matches = [
        row
        for row in components
        if isinstance(row, Mapping) and row.get("component_id") == COMPONENT_ID
    ]
    if (
        len(matches) != 1
        or matches[0].get("stage_id") != STAGE_ID
        or matches[0].get("preflight_api")
        != "preflight_closure_sealed_batch_component"
        or matches[0].get("execute_api")
        != "execute_closure_sealed_batch_component"
    ):
        raise ClosureThresholdSensitivityError("E3 component registry binding drifted")
    output_contracts = contract.get("component_output_contracts")
    expected_output_contract = {
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "output_tables": list(OUTPUT_TABLES),
        "required_nonempty_tables": list(REQUIRED_NONEMPTY_TABLES),
        "completed_nonempty_tables": [],
        "unavailable_nonempty_tables": [],
        "unavailable_empty_tables": [],
    }
    if (
        not isinstance(output_contracts, Sequence)
        or isinstance(output_contracts, (str, bytes))
        or list(output_contracts).count(expected_output_contract) != 1
    ):
        raise ClosureThresholdSensitivityError("E3 output table contract drifted")


def preflight_closure_sealed_batch_component(
    authority: Mapping[str, Any],
    sealed_batch_contract: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    """Validate source-independent E3 bindings without data or path access."""

    _require_authority(authority)
    _require_component_contract(sealed_batch_contract)
    if not isinstance(repo_root, Path):
        raise ClosureThresholdSensitivityError("E3 repository root is not a Path")
    return {
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "status": "ready",
        "contract_sha256": _contract_sha256(sealed_batch_contract),
        "outcome_paths_opened": False,
        "writes_performed": False,
    }


def _copy_context(batch_context: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(batch_context, Mapping) or set(batch_context) != CONTEXT_KEYS:
        raise ClosureThresholdSensitivityError("E3 batch_context keys drifted")
    execution_id = batch_context.get("execution_id")
    if type(execution_id) is not str or not execution_id:
        raise ClosureThresholdSensitivityError("E3 execution_id is malformed")
    if type(batch_context.get("rng_seed")) is not int or batch_context.get(
        "rng_seed"
    ) != RNG_SEED:
        raise ClosureThresholdSensitivityError("E3 RNG seed drifted")
    tables_raw = batch_context.get("tables")
    stages_raw = batch_context.get("stage_results")
    availability_raw = batch_context.get("model_availability")
    software_evidence_raw = batch_context.get("software_evidence")
    if not isinstance(tables_raw, Mapping) or not isinstance(stages_raw, Mapping):
        raise ClosureThresholdSensitivityError("E3 context mappings are malformed")
    if not isinstance(availability_raw, Mapping):
        raise ClosureThresholdSensitivityError("E3 availability mapping is malformed")
    if not isinstance(software_evidence_raw, Mapping):
        raise ClosureThresholdSensitivityError("E3 software evidence is malformed")
    if set(software_evidence_raw) != SOFTWARE_EVIDENCE_KEYS:
        raise ClosureThresholdSensitivityError("E3 software evidence keys drifted")
    tables: dict[str, pd.DataFrame] = {}
    for key, frame in tables_raw.items():
        if type(key) is not str or not key or not isinstance(frame, pd.DataFrame):
            raise ClosureThresholdSensitivityError("E3 table binding drifted")
        tables[key] = frame.copy(deep=True)
    stage_results: dict[str, dict[str, Any]] = {}
    for key, value in stages_raw.items():
        if type(key) is not str or not key or not isinstance(value, Mapping):
            raise ClosureThresholdSensitivityError("E3 stage-result binding drifted")
        stage_results[key] = dict(value)
    availability: dict[str, str] = {}
    for key, value in availability_raw.items():
        if type(key) is not str or value not in {"available", "unavailable"}:
            raise ClosureThresholdSensitivityError("E3 model availability drifted")
        availability[key] = cast(str, value)
    return {
        "execution_id": execution_id,
        "rng_seed": RNG_SEED,
        "tables": tables,
        "stage_results": stage_results,
        "model_availability": availability,
        "software_evidence": copy.deepcopy(dict(software_evidence_raw)),
    }


def _exact_integer(series: pd.Series, *, name: str) -> pd.Series:
    numeric = pd.to_numeric(series, errors="raise")
    values = numeric.to_numpy(dtype="float64")
    if not np.isfinite(values).all() or not np.equal(values, np.floor(values)).all():
        raise ClosureThresholdSensitivityError(f"E3 {name} is not exact integer")
    return numeric.astype("int64")


def _prediction_frame(frame: pd.DataFrame) -> pd.DataFrame:
    missing = set(PREDICTION_REQUIRED_COLUMNS).difference(frame.columns)
    if missing:
        raise ClosureThresholdSensitivityError(
            f"E3 prediction columns missing: {sorted(missing)}"
        )
    value = frame.copy(deep=True)
    if value.empty:
        raise ClosureThresholdSensitivityError("E3 prediction surface is empty")
    text_columns = (
        "source_id",
        "site_id",
        "common_origin_id",
        "model_id",
        "evaluation_cohort",
        "evaluation_role",
        "terminal_status",
    )
    for column in text_columns:
        if value[column].isna().any() or (value[column].astype(str).str.len() == 0).any():
            raise ClosureThresholdSensitivityError(f"E3 {column} is malformed")
        value[column] = value[column].astype(str)
    value["horizon_months"] = _exact_integer(value["horizon_months"], name="horizon")
    value["model_seed"] = _exact_integer(value["model_seed"], name="model seed")
    value["seed_slot"] = _exact_integer(value["seed_slot"], name="seed slot")
    if not value["horizon_months"].isin(HORIZONS).all():
        raise ClosureThresholdSensitivityError("E3 horizon drifted")
    duplicate_columns = [*PREDICTION_KEY_COLUMNS, "evaluation_role"]
    if value.duplicated(duplicate_columns).any():
        raise ClosureThresholdSensitivityError("E3 duplicate prediction rows")
    if not set(EVALUATION_COHORTS).issubset(set(value["evaluation_cohort"])):
        raise ClosureThresholdSensitivityError("E3 evaluation cohorts are incomplete")
    if VALIDATION_ROLE not in set(value["evaluation_role"]):
        raise ClosureThresholdSensitivityError("E3 validation role is absent")
    if not value["evaluation_role"].isin([VALIDATION_ROLE, TEST_ROLE]).all():
        raise ClosureThresholdSensitivityError("E3 evaluation role drifted")
    value["continuous_score"] = pd.to_numeric(value["continuous_score"], errors="coerce")
    value["actual_value"] = pd.to_numeric(value["actual_value"], errors="coerce")
    success = value["terminal_status"].eq("success")
    if value.loc[success, ["continuous_score", "actual_value"]].isna().any().any():
        raise ClosureThresholdSensitivityError("E3 successful prediction is incomplete")
    finite = value.loc[success, ["continuous_score", "actual_value"]].to_numpy(
        dtype="float64"
    )
    if finite.size and not np.isfinite(finite).all():
        raise ClosureThresholdSensitivityError("E3 successful values are nonfinite")
    for model_id, status in value.groupby("model_id", sort=True)["terminal_status"]:
        expected = cast(str, model_id)
        if status.eq("success").any():
            continue
        if not status.eq("model_unavailable").all():
            raise ClosureThresholdSensitivityError(
                f"E3 unavailable terminal dialect drifted: {expected}"
            )
    return value.sort_values(duplicate_columns, kind="mergesort").reset_index(drop=True)


def _target_surface(predictions: pd.DataFrame) -> pd.DataFrame:
    identity = [
        "source_id",
        "site_id",
        "common_origin_id",
        "horizon_months",
        "evaluation_cohort",
        "evaluation_role",
    ]
    available = predictions.loc[predictions["actual_value"].notna(), [*identity, "actual_value"]]
    if available.empty:
        raise ClosureThresholdSensitivityError("E3 has no locked continuous outcomes")
    consistency = available.groupby(identity, sort=True, dropna=False)["actual_value"].nunique()
    if (consistency != 1).any():
        raise ClosureThresholdSensitivityError("E3 locked outcome drifted across models")
    return available.drop_duplicates(identity).sort_values(identity, kind="mergesort").reset_index(drop=True)


def _fit_calibrator(
    scores: np.ndarray, labels: np.ndarray
) -> tuple[LogisticRegression, float] | None:
    if scores.size == 0 or np.unique(labels).size != 2:
        return None
    estimator = LogisticRegression(
        C=1.0,
        fit_intercept=True,
        max_iter=1000,
        random_state=RNG_SEED,
        solver="lbfgs",
        tol=1e-12,
    )
    estimator.fit(scores.reshape(-1, 1), labels)
    calibrated = estimator.predict_proba(scores.reshape(-1, 1))[:, 1]
    candidates = np.unique(np.concatenate(([0.0], calibrated, [1.0])))
    best_score = -1.0
    best_threshold = 1.0
    for candidate in candidates:
        score = float(
            fbeta_score(labels, calibrated >= candidate, beta=2.0, zero_division=0)
        )
        if score > best_score or (score == best_score and candidate > best_threshold):
            best_score = score
            best_threshold = float(candidate)
    return estimator, best_threshold


def _calibration_curve(labels: np.ndarray, probabilities: np.ndarray) -> list[dict[str, Any]]:
    edges = np.linspace(0.0, 1.0, 11)
    bins = np.minimum(np.searchsorted(edges, probabilities, side="right") - 1, 9)
    rows: list[dict[str, Any]] = []
    for index in range(10):
        mask = bins == index
        if not mask.any():
            continue
        rows.append(
            {
                "bin": index,
                "lower": float(edges[index]),
                "upper": float(edges[index + 1]),
                "count": int(mask.sum()),
                "mean_probability": float(np.mean(probabilities[mask])),
                "observed_rate": float(np.mean(labels[mask])),
            }
        )
    return rows


def _prevalence_table(targets: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = ["evaluation_cohort", "evaluation_role", "horizon_months"]
    for key, group in targets.groupby(group_columns, sort=True):
        key_values = cast(tuple[Any, ...], key)
        for threshold in THRESHOLDS_UG_L:
            positive = group["actual_value"].to_numpy(dtype="float64") >= threshold
            positive_sites = group.loc[positive, ["source_id", "site_id"]].drop_duplicates()
            rows.append(
                {
                    **dict(zip(group_columns, key_values, strict=True)),
                    "threshold_ug_l": threshold,
                    "origin_count": int(len(group)),
                    "positive_count": int(positive.sum()),
                    "positive_rate": float(np.mean(positive)),
                    "positive_site_count": int(len(positive_sites)),
                }
            )
    return pd.DataFrame(rows).sort_values(
        [*group_columns, "threshold_ug_l"], kind="mergesort"
    ).reset_index(drop=True)


def _evaluate_thresholds(
    predictions: pd.DataFrame, availability: Mapping[str, str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    metrics: list[dict[str, Any]] = []
    scored_rows: list[pd.DataFrame] = []
    identity = ["model_id", "model_seed", "seed_slot", "horizon_months"]
    for key, group in predictions.groupby(identity, sort=True):
        key_values = cast(tuple[Any, ...], key)
        model_id = str(key_values[0])
        model_available = availability.get(model_id) == "available"
        validation = group.loc[
            group["evaluation_role"].eq(VALIDATION_ROLE)
            & group["terminal_status"].eq("success")
        ]
        tests = group.loc[group["evaluation_role"].eq(TEST_ROLE)].copy()
        for threshold in THRESHOLDS_UG_L:
            fitted: tuple[LogisticRegression, float] | None = None
            if model_available and not validation.empty:
                labels = (
                    validation["actual_value"].to_numpy(dtype="float64") >= threshold
                ).astype("int64")
                fitted = _fit_calibrator(
                    validation["continuous_score"].to_numpy(dtype="float64"), labels
                )
            for cohort in EVALUATION_COHORTS:
                cohort_rows = tests.loc[tests["evaluation_cohort"].eq(cohort)].copy()
                successful = cohort_rows.loc[cohort_rows["terminal_status"].eq("success")]
                base = {
                    **dict(zip(identity, key_values, strict=True)),
                    "threshold_ug_l": threshold,
                    "evaluation_cohort": cohort,
                    "origin_count": int(len(cohort_rows)),
                    "successful_origin_count": int(len(successful)),
                    "terminal_status": "success",
                    "decision_threshold": None,
                    "positive_count": None,
                    "positive_rate": None,
                    "pr_auc": None,
                    "brier": None,
                    "recall": None,
                    "precision": None,
                    "f2": None,
                    "alert_rate": None,
                    "calibration_curve_json": "[]",
                }
                if not model_available or cohort_rows.empty:
                    base["terminal_status"] = "model_unavailable"
                    metrics.append(base)
                    continue
                if fitted is None or successful.empty:
                    base["terminal_status"] = "calibration_unavailable"
                    metrics.append(base)
                    continue
                estimator, decision_threshold = fitted
                labels = (
                    successful["actual_value"].to_numpy(dtype="float64") >= threshold
                ).astype("int64")
                probabilities = estimator.predict_proba(
                    successful["continuous_score"].to_numpy(dtype="float64").reshape(-1, 1)
                )[:, 1]
                alerts = probabilities >= decision_threshold
                base.update(
                    {
                        "decision_threshold": decision_threshold,
                        "positive_count": int(labels.sum()),
                        "positive_rate": float(np.mean(labels)),
                        "pr_auc": (
                            float(average_precision_score(labels, probabilities))
                            if np.unique(labels).size == 2
                            else None
                        ),
                        "brier": float(brier_score_loss(labels, probabilities)),
                        "recall": float(recall_score(labels, alerts, zero_division=0)),
                        "precision": float(
                            precision_score(labels, alerts, zero_division=0)
                        ),
                        "f2": float(
                            fbeta_score(labels, alerts, beta=2.0, zero_division=0)
                        ),
                        "alert_rate": float(np.mean(alerts)),
                        "calibration_curve_json": json.dumps(
                            _calibration_curve(labels, probabilities),
                            sort_keys=True,
                            separators=(",", ":"),
                            allow_nan=False,
                        ),
                    }
                )
                scored = successful.loc[
                    :,
                    [
                        "source_id",
                        "site_id",
                        "common_origin_id",
                        "horizon_months",
                        "model_id",
                        "model_seed",
                        "seed_slot",
                        "evaluation_cohort",
                    ],
                ].copy()
                scored["threshold_ug_l"] = threshold
                scored["actual_bloom"] = labels
                scored["calibrated_probability"] = probabilities
                scored["decision_threshold"] = decision_threshold
                scored["alert"] = alerts.astype("int64")
                scored_rows.append(scored)
                metrics.append(base)
    metric_frame = pd.DataFrame(metrics).sort_values(
        [*identity, "threshold_ug_l", "evaluation_cohort"], kind="mergesort"
    ).reset_index(drop=True)
    scored_frame = (
        pd.concat(scored_rows, ignore_index=True)
        if scored_rows
        else pd.DataFrame(
            columns=[
                "source_id",
                "site_id",
                "common_origin_id",
                "horizon_months",
                "model_id",
                "model_seed",
                "seed_slot",
                "evaluation_cohort",
                "threshold_ug_l",
                "actual_bloom",
                "calibrated_probability",
                "decision_threshold",
                "alert",
            ]
        )
    )
    return metric_frame, scored_frame


def _pairwise_differences(metrics: pd.DataFrame, scored: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    key_columns = ["threshold_ug_l", "horizon_months", "evaluation_cohort"]
    for key, metric_group in metrics.groupby(key_columns, sort=True):
        key_values = cast(tuple[Any, ...], key)
        for left_model, right_model in MODEL_PAIRS:
            slots = sorted(
                set(
                    metric_group.loc[
                        metric_group["model_id"].isin([left_model, right_model]),
                        "seed_slot",
                    ].astype("int64")
                )
            )
            if not slots:
                slots = [RNG_SEED]
            for seed_slot in slots:
                seed_group = metric_group.loc[metric_group["seed_slot"].eq(seed_slot)]
                for metric in (
                    "pr_auc",
                    "brier",
                    "recall",
                    "precision",
                    "f2",
                    "alert_rate",
                ):
                    left = seed_group.loc[seed_group["model_id"].eq(left_model), metric]
                    right = seed_group.loc[seed_group["model_id"].eq(right_model), metric]
                    estimable = bool(
                        len(left) == 1
                        and len(right) == 1
                        and pd.notna(left.iloc[0])
                        and pd.notna(right.iloc[0])
                    )
                    paired_count = 0
                    if not scored.empty:
                        surface = scored.loc[
                            scored["threshold_ug_l"].eq(key_values[0])
                            & scored["horizon_months"].eq(key_values[1])
                            & scored["evaluation_cohort"].eq(key_values[2])
                            & scored["seed_slot"].eq(seed_slot)
                            & scored["model_id"].isin([left_model, right_model])
                        ]
                        paired_count = int(
                            surface.groupby(
                                ["source_id", "site_id", "common_origin_id"],
                                sort=True,
                            )["model_id"]
                            .nunique()
                            .eq(2)
                            .sum()
                        )
                    left_value = float(cast(Any, left.iloc[0])) if estimable else None
                    right_value = float(cast(Any, right.iloc[0])) if estimable else None
                    rows.append(
                        {
                            **dict(zip(key_columns, key_values, strict=True)),
                            "seed_slot": int(seed_slot),
                            "left_model_id": left_model,
                            "right_model_id": right_model,
                            "metric": metric,
                            "left_value": left_value,
                            "right_value": right_value,
                            "difference_left_minus_right": (
                                cast(float, left_value) - cast(float, right_value)
                                if estimable
                                else None
                            ),
                            "paired_origin_count": paired_count,
                            "estimable": bool(estimable and paired_count > 0),
                        }
                    )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["benefit_left_over_right"] = np.where(
        result["metric"].eq("brier"),
        -pd.to_numeric(result["difference_left_minus_right"], errors="coerce"),
        pd.to_numeric(result["difference_left_minus_right"], errors="coerce"),
    )
    robustness_keys = [
        "seed_slot",
        "horizon_months",
        "evaluation_cohort",
        "left_model_id",
        "right_model_id",
        "metric",
    ]
    estimable = result["estimable"] & result["benefit_left_over_right"].notna()
    result["_positive"] = estimable & result["benefit_left_over_right"].gt(0.0)
    result["_negative"] = estimable & result["benefit_left_over_right"].lt(0.0)
    result["_estimable"] = estimable
    grouped = result.groupby(robustness_keys, sort=True, dropna=False)
    result["estimable_threshold_count"] = grouped["_estimable"].transform("sum").astype("int64")
    result["positive_sign_threshold_count"] = grouped["_positive"].transform("sum").astype("int64")
    result["negative_sign_threshold_count"] = grouped["_negative"].transform("sum").astype("int64")
    result["sign_stable_at_least_3_of_4"] = result[
        ["positive_sign_threshold_count", "negative_sign_threshold_count"]
    ].max(axis=1).ge(3)
    result = result.drop(columns=["_positive", "_negative", "_estimable"])
    return result.sort_values(
        [*key_columns, "seed_slot", "left_model_id", "right_model_id", "metric"],
        kind="mergesort",
    ).reset_index(drop=True)


def _kendall_tau(left: Mapping[str, float], right: Mapping[str, float]) -> float | None:
    keys = sorted(set(left).intersection(right))
    if len(keys) < 2:
        return None
    concordant = 0
    discordant = 0
    left_ties = 0
    right_ties = 0
    for index, first in enumerate(keys):
        for second in keys[index + 1 :]:
            left_delta = left[first] - left[second]
            right_delta = right[first] - right[second]
            if left_delta == 0 and right_delta == 0:
                continue
            if left_delta == 0:
                left_ties += 1
            elif right_delta == 0:
                right_ties += 1
            elif left_delta * right_delta > 0:
                concordant += 1
            else:
                discordant += 1
    denominator = math.sqrt(
        (concordant + discordant + left_ties)
        * (concordant + discordant + right_ties)
    )
    return None if denominator == 0 else float((concordant - discordant) / denominator)


def _rank_stability(metrics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for raw_key, group in metrics.groupby(
        ["horizon_months", "evaluation_cohort"], sort=True
    ):
        horizon, cohort = cast(tuple[Any, Any], raw_key)
        for metric, ascending in (("pr_auc", False), ("brier", True), ("f2", False)):
            reference_rows = group.loc[
                group["threshold_ug_l"].eq(PRIMARY_THRESHOLD_UG_L)
                & group[metric].notna()
            ].copy()
            reference_rows["model_key"] = (
                reference_rows["model_id"].astype(str)
                + ":"
                + reference_rows["seed_slot"].astype(str)
            )
            reference_rows["rank"] = reference_rows[metric].rank(
                method="average", ascending=ascending
            )
            reference = dict(zip(reference_rows["model_key"], reference_rows["rank"], strict=True))
            for threshold in THRESHOLDS_UG_L:
                compared = group.loc[
                    group["threshold_ug_l"].eq(threshold) & group[metric].notna()
                ].copy()
                compared["model_key"] = (
                    compared["model_id"].astype(str)
                    + ":"
                    + compared["seed_slot"].astype(str)
                )
                compared["rank"] = compared[metric].rank(
                    method="average", ascending=ascending
                )
                observed = dict(zip(compared["model_key"], compared["rank"], strict=True))
                common = set(reference).intersection(observed)
                rows.append(
                    {
                        "horizon_months": int(horizon),
                        "evaluation_cohort": str(cohort),
                        "metric": metric,
                        "reference_threshold_ug_l": PRIMARY_THRESHOLD_UG_L,
                        "compared_threshold_ug_l": threshold,
                        "compared_model_count": len(common),
                        "kendall_tau": _kendall_tau(reference, observed),
                        "estimable": len(common) >= 2,
                    }
                )
    return pd.DataFrame(rows).sort_values(
        ["horizon_months", "evaluation_cohort", "metric", "compared_threshold_ug_l"],
        kind="mergesort",
    ).reset_index(drop=True)


def _report(
    prevalence: pd.DataFrame,
    metrics: pd.DataFrame,
    pairwise: pd.DataFrame,
    ranks: pd.DataFrame,
) -> str:
    estimable_pairs = int(pairwise["estimable"].sum())
    robust_pair_groups = int(
        pairwise.drop_duplicates(
            [
                "seed_slot",
                "horizon_months",
                "evaluation_cohort",
                "left_model_id",
                "right_model_id",
                "metric",
            ]
        )["sign_stable_at_least_3_of_4"].sum()
    )
    estimable_ranks = int(ranks["estimable"].sum())
    unavailable = int(metrics["terminal_status"].ne("success").sum())
    severe = prevalence.loc[prevalence["threshold_ug_l"].eq(50.0)]
    severe_positives = int(severe["positive_count"].sum())
    return (
        "# Closure V1 E3 threshold sensitivity\n\n"
        "Temporal scores were held fixed. Independent Platt calibrators and "
        "decision thresholds were fitted on validation rows only.\n\n"
        f"- predeclared thresholds: {', '.join(str(int(v)) for v in THRESHOLDS_UG_L)} ug/L\n"
        f"- terminal unavailable metric rows retained: {unavailable}\n"
        f"- estimable paired comparisons: {estimable_pairs}\n"
        f"- comparison groups with sign stable in at least 3/4 thresholds: {robust_pair_groups}\n"
        f"- estimable Kendall comparisons: {estimable_ranks}\n"
        f"- observed positives at 50 ug/L across reported cohorts: {severe_positives}\n"
        "- P0/P1/A2 are never replaced by another model.\n"
        "- B2 threshold-specific retraining is not performed in this primary fixed-score analysis.\n"
        "- A sparse 50 ug/L endpoint is reported as imprecise, never removed post hoc.\n"
    )


def _artifact(format_name: str, payload: Any, *, manifest_last: bool = False) -> dict[str, Any]:
    return {"format": format_name, "payload": payload, "manifest_last": manifest_last}


def validate_threshold_sensitivity_result(result: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "component_id",
        "stage_id",
        "status",
        "artifacts",
        "tables",
        "diagnostics",
        "outcome_paths_opened",
        "writes_performed",
    }
    if not isinstance(result, Mapping) or set(result) != required:
        raise ClosureThresholdSensitivityError("E3 result keys drifted")
    if result.get("component_id") != COMPONENT_ID or result.get("stage_id") != STAGE_ID:
        raise ClosureThresholdSensitivityError("E3 result identity drifted")
    if result.get("status") not in {"completed", "completed_unavailable"}:
        raise ClosureThresholdSensitivityError("E3 result status drifted")
    if result.get("outcome_paths_opened") is not True or result.get(
        "writes_performed"
    ) is not False:
        raise ClosureThresholdSensitivityError("E3 result I/O flags drifted")
    artifacts = result.get("artifacts")
    if not isinstance(artifacts, Mapping) or set(artifacts) != set(OUTPUT_PATHS):
        raise ClosureThresholdSensitivityError("E3 artifact path set drifted")
    manifest_last_count = 0
    for path, envelope in artifacts.items():
        if not isinstance(envelope, Mapping) or set(envelope) != {
            "format",
            "payload",
            "manifest_last",
        }:
            raise ClosureThresholdSensitivityError(f"E3 envelope drifted: {path}")
        if envelope["format"] not in {"csv", "json", "markdown", "parquet", "xml"}:
            raise ClosureThresholdSensitivityError(f"E3 format drifted: {path}")
        if type(envelope["manifest_last"]) is not bool:
            raise ClosureThresholdSensitivityError(f"E3 manifest flag drifted: {path}")
        manifest_last_count += int(envelope["manifest_last"])
    if manifest_last_count != 1:
        raise ClosureThresholdSensitivityError("E3 requires one final report sentinel")
    tables = result.get("tables")
    if not isinstance(tables, Mapping) or set(tables) != set(OUTPUT_TABLES):
        raise ClosureThresholdSensitivityError("E3 output table set drifted")
    for name, frame in tables.items():
        if type(frame) is not pd.DataFrame:
            raise ClosureThresholdSensitivityError(
                f"E3 output table type drifted: {name}"
            )
    for name in REQUIRED_NONEMPTY_TABLES:
        if cast(pd.DataFrame, tables[name]).empty:
            raise ClosureThresholdSensitivityError(
                f"E3 required output table is empty: {name}"
            )
    return dict(result)


def execute_closure_sealed_batch_component(
    authority: Mapping[str, Any],
    sealed_batch_contract: Mapping[str, Any],
    batch_context: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    """Evaluate all four thresholds in memory; publication remains runner-owned."""

    preflight_closure_sealed_batch_component(authority, sealed_batch_contract, repo_root)
    context = _copy_context(batch_context)
    sealed_availability = sealed_batch_contract.get("model_availability")
    if not isinstance(sealed_availability, Mapping) or dict(
        cast(Mapping[str, Any], context["model_availability"])
    ) != dict(sealed_availability):
        raise ClosureThresholdSensitivityError(
            "E3 model availability is not batch-bound"
        )
    tables = cast(dict[str, pd.DataFrame], context["tables"])
    if "predictions_long" not in tables:
        raise ClosureThresholdSensitivityError("E3 predictions_long table is absent")
    predictions = _prediction_frame(tables["predictions_long"])
    targets = _target_surface(predictions)
    prevalence = _prevalence_table(targets)
    metrics, scored = _evaluate_thresholds(
        predictions, cast(dict[str, str], context["model_availability"])
    )
    pairwise = _pairwise_differences(metrics, scored)
    ranks = _rank_stability(metrics)
    report = _report(prevalence, metrics, pairwise, ranks)
    status = (
        "completed"
        if metrics["terminal_status"].eq("success").all()
        else "completed_unavailable"
    )
    artifacts = {
        OUTPUT_PATHS[0]: _artifact("csv", prevalence.copy(deep=True)),
        OUTPUT_PATHS[1]: _artifact("csv", metrics.copy(deep=True)),
        OUTPUT_PATHS[2]: _artifact("csv", pairwise.copy(deep=True)),
        OUTPUT_PATHS[3]: _artifact("csv", ranks.copy(deep=True)),
        OUTPUT_PATHS[4]: _artifact("markdown", report, manifest_last=True),
    }
    result = {
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "status": status,
        "artifacts": artifacts,
        "tables": {
            "e3_threshold_prevalence": prevalence.copy(deep=True),
            "e3_threshold_metrics": metrics.copy(deep=True),
            "e3_threshold_pairwise": pairwise.copy(deep=True),
            "e3_rank_stability": ranks.copy(deep=True),
        },
        "diagnostics": {
            "execution_id": context["execution_id"],
            "thresholds_ug_l": list(THRESHOLDS_UG_L),
            "primary_threshold_ug_l": PRIMARY_THRESHOLD_UG_L,
            "model_scores_refit": False,
            "validation_only_calibration": True,
            "b2_secondary_retraining_performed": False,
            "writes_performed": False,
        },
        "outcome_paths_opened": True,
        "writes_performed": False,
    }
    return validate_threshold_sensitivity_result(result)
