#!/usr/bin/env python
"""Pure common-mask matched PIPE–MIFAL degradation component for E6."""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from pathlib import Path
from typing import Any, Mapping, cast

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, fbeta_score, recall_score


COMPONENT_ID = "E6_matched_degradation"
STAGE_ID = "E6"
RAW_TABLE = "degradation_raw_cells"
PREDICTION_TABLE = "degradation_predictions"
SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
RAW_VARIABLES = ("mean_TP_ugL", "mean_TN_ugL", "mean_DO_mgL", "mean_pH", "mean_turbidity_NTU", "mean_secchi_depth_m", "mean_temperature_C")
SCENARIOS = ("control", "mcar_10", "mcar_25", "mcar_50", "block_1m_10", "block_3m_10", "block_6m_25", "ablate_nutrients", "ablate_physchem", "ablate_light", "ablate_temperature", "combined_moderate", "combined_severe")
TARGET_EVENTS = ("bloom_h", "irc_alert_h")
RAW_COLUMNS = ("source_id", "site_id", "holdout_group_id", "common_origin_id", "year_month", "horizon_months", "raw_variable", "value")
PREDICTION_COLUMNS = ("scenario_id", "degradation_seed", "source_id", "site_id", "holdout_group_id", "common_origin_id", "horizon_months", "model_id", "model_seed", "target_event", "actual", "score", "threshold", "terminal_status", "mask_sha256")
OUTPUT_PATHS = ("data/closure_v1/degradation_masks.parquet", "reports/closure_v1/06_degradation/matched_degradation_metrics.csv", "reports/closure_v1/06_degradation/matched_degradation_pairwise.csv", "reports/closure_v1/06_degradation/failure_registry.csv", "reports/closure_v1/06_degradation/robustness_auc.csv", "reports/closure_v1/06_degradation/matched_degradation_report.md")
COMPONENT_CONTRACT = {"schema_version": "closure_e6_matched_degradation_v1", "component_id": COMPONENT_ID, "stage_id": STAGE_ID, "input_tables": [RAW_TABLE, PREDICTION_TABLE], "raw_columns": list(RAW_COLUMNS), "prediction_columns": list(PREDICTION_COLUMNS), "scenarios": list(SCENARIOS), "ordered_seed_slots": list(SEEDS), "target_events": list(TARGET_EVENTS), "raw_variables": list(RAW_VARIABLES), "mask_digest": "sha256_first8_big_endian_divide_2pow64", "mask_tuple": ["closure_v1", "E6", "scenario_id", "seed", "source_id", "site_id", "year_month", "variable"], "common_mask_models": ["M0", "P1"], "model_seed_cross_product": "forbidden", "m0_model_seed": 1729, "p1_seed_slot_pairing": "one_to_one", "derived_lineage_invalidation_before_transform": True, "refit_under_degradation": "forbidden", "output_paths": list(OUTPUT_PATHS), "filesystem_writes": "forbidden"}


class MatchedDegradationError(RuntimeError):
    pass


def _digest(value: Mapping[str, Any]) -> str:
    payload = (
        json.dumps(
            dict(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def component_contract() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(json.dumps(COMPONENT_CONTRACT)))


def component_contract_sha256() -> str:
    return _digest(COMPONENT_CONTRACT)


def _validate(authority: Mapping[str, Any], contract: Mapping[str, Any]) -> str:
    required = {"gate": "E0-U", "effective_authority": True, "sealed_batch_execution_authorized": True, "e0_m_authorized": True, "e0_u_authorized": True, "evaluation_authorized": True, "outcome_access_authorized": True, "writes_performed": False}
    if any(type(authority.get(k)) is not type(v) or authority.get(k) != v for k, v in required.items()):
        raise MatchedDegradationError("E6 E0-U authority drifted")
    expected = {"component_id": COMPONENT_ID, "stage_id": STAGE_ID, "module_name": "src.experiments.evaluate_matched_degradation", "source_path": "src/experiments/evaluate_matched_degradation.py", "preflight_api": "preflight_closure_sealed_batch_component", "execute_api": "execute_closure_sealed_batch_component"}
    if contract.get("schema_version") != "closure_sealed_evaluation_batch_v1" or contract.get("experiment_id") != "closure_v1" or contract.get("execution_gate") != "E0-U" or contract.get("evaluation_refit") != "forbidden" or contract.get("failed_model_replacement") != "forbidden" or contract.get("silent_row_deletion") != "forbidden" or contract.get("one_batch_only") is not True or authority.get("sealed_batch_command") != contract.get("sealed_command") or not isinstance(contract.get("components"), list) or cast(list[Any], contract["components"]).count(expected) != 1:
        raise MatchedDegradationError("E6 sealed batch contract drifted")
    return _digest(contract)


def preflight_closure_sealed_batch_component(authority: Mapping[str, Any], sealed_batch_contract: Mapping[str, Any], repo_root: Path | None = None) -> dict[str, Any]:
    del repo_root
    return {"component_id": COMPONENT_ID, "stage_id": STAGE_ID, "status": "ready", "contract_sha256": _validate(authority, sealed_batch_contract), "outcome_paths_opened": False, "writes_performed": False}


def _payload(scenario: str, seed: int, source: str, site: str, month: str, variable: str) -> bytes:
    values = ["closure_v1", "E6", scenario, seed, unicodedata.normalize("NFC", source), unicodedata.normalize("NFC", site), month, variable]
    return json.dumps(values, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()


def _uniform(scenario: str, seed: int, source: str, site: str, month: str, variable: str) -> float:
    digest = hashlib.sha256(_payload(scenario, seed, source, site, month, variable)).digest()
    return int.from_bytes(digest[:8], "big", signed=False) / 18446744073709551616.0


def _mcar_mask(frame: pd.DataFrame, scenario: str, seed: int, fraction: float) -> pd.Series:
    values = [
        _uniform(
            scenario,
            seed,
            str(row["source_id"]),
            str(row["site_id"]),
            str(row["year_month"]),
            str(row["raw_variable"]),
        )
        < fraction
        for row in frame.to_dict("records")
    ]
    return pd.Series(values, index=frame.index, dtype="bool") & pd.to_numeric(frame["value"], errors="coerce").map(np.isfinite)


def _block_mask(frame: pd.DataFrame, scenario: str, seed: int, length: int, fraction: float) -> pd.Series:
    masked = pd.Series(False, index=frame.index, dtype="bool")
    for raw_group_key, group in frame.groupby(
        ["source_id", "site_id", "raw_variable"], sort=True
    ):
        source, site, variable = cast(tuple[Any, Any, Any], raw_group_key)
        observed = group[pd.to_numeric(group["value"], errors="coerce").map(np.isfinite)].copy()
        if observed.empty:
            continue
        observed["period"] = pd.PeriodIndex(observed["year_month"].astype(str), freq="M")
        observed = observed.sort_values("period").drop_duplicates("period")
        span = pd.period_range(observed["period"].min(), observed["period"].max(), freq="M")
        observed_periods = set(observed["period"])
        candidates = [
            start
            for start in span
            if start + (length - 1) <= span[-1]
            and all(start + offset in observed_periods for offset in range(length))
        ]
        target = max(1, math.floor(fraction * len(observed) / length + 0.5)) if candidates else 0
        ordered = sorted(candidates, key=lambda start: (_uniform(scenario, seed, str(source), str(site), str(start), str(variable)), start))
        selected: list[pd.Period] = []
        occupied: set[pd.Period] = set()
        for start in ordered:
            months = {start + offset for offset in range(length)}
            if months & occupied:
                continue
            selected.append(start)
            occupied.update(months)
            if len(selected) == target:
                break
        periods = pd.PeriodIndex(group["year_month"].astype(str), freq="M")
        masked.loc[group.index] = periods.isin(occupied) & pd.to_numeric(group["value"], errors="coerce").map(np.isfinite).to_numpy()
    return masked


def build_common_degradation_masks(raw: pd.DataFrame) -> pd.DataFrame:
    if tuple(raw.columns) != RAW_COLUMNS:
        raise MatchedDegradationError("E6 raw-cell columns are not exact")
    if raw.duplicated(["source_id", "site_id", "common_origin_id", "year_month", "horizon_months", "raw_variable"]).any() or not raw["raw_variable"].isin(RAW_VARIABLES).all() or not raw["horizon_months"].isin([1, 2, 3]).all():
        raise MatchedDegradationError("E6 raw-cell universe is not exact and unique")
    physical = ["source_id", "site_id", "year_month", "raw_variable"]
    value_drift = raw.groupby(physical, sort=True, dropna=False)["value"].nunique(dropna=False)
    if (value_drift > 1).any():
        raise MatchedDegradationError("E6 repeated raw physical cell has conflicting values")
    rows: list[pd.DataFrame] = []
    ablations = {"ablate_nutrients": {"mean_TP_ugL", "mean_TN_ugL"}, "ablate_physchem": {"mean_DO_mgL", "mean_pH"}, "ablate_light": {"mean_turbidity_NTU", "mean_secchi_depth_m"}, "ablate_temperature": {"mean_temperature_C"}}
    for scenario in SCENARIOS:
        seeds = SEEDS
        for seed in seeds:
            if scenario == "control":
                mask = pd.Series(False, index=raw.index)
            elif scenario.startswith("mcar_"):
                mask = _mcar_mask(raw, scenario, seed, int(scenario.split("_")[1]) / 100.0)
            elif scenario.startswith("block_"):
                parts = scenario.split("_")
                mask = _block_mask(raw, scenario, seed, int(parts[1].removesuffix("m")), int(parts[2]) / 100.0)
            elif scenario in ablations:
                mask = raw["raw_variable"].isin(ablations[scenario]) & pd.to_numeric(raw["value"], errors="coerce").map(np.isfinite)
            elif scenario == "combined_moderate":
                mask = _mcar_mask(raw, "mcar_25", seed, 0.25) | _block_mask(raw, "block_3m_10", seed, 3, 0.10)
            elif scenario == "combined_severe":
                mask = _mcar_mask(raw, "mcar_50", seed, 0.50) | _block_mask(raw, "block_6m_25", seed, 6, 0.25) | (raw["raw_variable"].isin(ablations["ablate_nutrients"]) & pd.to_numeric(raw["value"], errors="coerce").map(np.isfinite))
            else:
                raise MatchedDegradationError(f"unknown E6 scenario: {scenario}")
            part = raw.loc[:, list(RAW_COLUMNS[:-1])].copy()
            part.insert(0, "scenario_id", scenario)
            part.insert(1, "degradation_seed", seed)
            eligible = pd.to_numeric(raw["value"], errors="coerce").map(np.isfinite)
            part["eligible"] = eligible.to_numpy(dtype="bool")
            part["masked"] = mask.to_numpy(dtype="bool")
            part["realized_fraction"] = (
                float(mask.sum() / eligible.sum()) if eligible.any() else 0.0
            )
            rows.append(part)
    result = pd.concat(rows, ignore_index=True)
    result["scenario_id"] = pd.Categorical(result["scenario_id"], categories=SCENARIOS, ordered=True)
    return result.sort_values(["scenario_id", "degradation_seed", "source_id", "site_id", "common_origin_id", "year_month", "horizon_months", "raw_variable"], kind="mergesort").reset_index(drop=True)


def _mask_digests(masks: pd.DataFrame) -> dict[tuple[str, int], str]:
    digests: dict[tuple[str, int], str] = {}
    for raw_key, group in masks.groupby(
        ["scenario_id", "degradation_seed"], sort=True
    ):
        key = cast(tuple[Any, Any], raw_key)
        records = group.assign(scenario_id=group["scenario_id"].astype(str)).to_dict("records")
        payload = json.dumps(records, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
        digests[(str(key[0]), int(key[1]))] = hashlib.sha256(payload).hexdigest()
    return digests


def _metric_rows(predictions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    metrics: list[dict[str, Any]] = []
    failures = predictions[predictions["terminal_status"] != "success"].copy()
    keys = ["scenario_id", "degradation_seed", "horizon_months", "target_event", "model_id", "model_seed"]
    for raw_key, full_group in predictions.groupby(keys, sort=True):
        key = cast(tuple[Any, Any, Any, Any, Any, Any], raw_key)
        scenario, seed, horizon, endpoint, model, model_seed = key
        group = full_group[full_group["terminal_status"] == "success"]
        actual = pd.to_numeric(group["actual"], errors="coerce")
        score = pd.to_numeric(group["score"], errors="coerce")
        threshold = pd.to_numeric(group["threshold"], errors="coerce")
        keep = actual.isin([0, 1]) & score.notna() & threshold.notna()
        actual = actual[keep].astype(int)
        score = score[keep].clip(0, 1)
        predicted = (score >= threshold[keep]).astype(int)
        metrics.append({"scenario_id": scenario, "degradation_seed": int(seed), "horizon_months": int(horizon), "target_event": endpoint, "model_id": model, "model_seed": int(model_seed), "rows": len(actual), "site_count": int(group.loc[keep, ["source_id", "site_id"]].drop_duplicates().shape[0]), "pr_auc": float(average_precision_score(actual, score)) if actual.nunique() == 2 else np.nan, "brier": float(brier_score_loss(actual, score)) if len(actual) else np.nan, "recall": float(recall_score(actual, predicted, zero_division=0)) if len(actual) else np.nan, "f2": float(fbeta_score(actual, predicted, beta=2, zero_division=0)) if len(actual) else np.nan, "availability": float(len(actual) / len(full_group)) if len(full_group) else np.nan, "failure_rate": float(1.0 - len(actual) / len(full_group)) if len(full_group) else np.nan})
    return pd.DataFrame(metrics), failures


def _validate_prediction_universe(predictions: pd.DataFrame) -> None:
    pair_identity = [
        "scenario_id",
        "degradation_seed",
        "source_id",
        "site_id",
        "holdout_group_id",
        "common_origin_id",
        "horizon_months",
        "target_event",
    ]
    if predictions.duplicated(pair_identity + ["model_id"]).any():
        raise MatchedDegradationError("E6 prediction/model rows are not unique")
    if (
        set(predictions["scenario_id"]) != set(SCENARIOS)
        or set(predictions["degradation_seed"]) != set(SEEDS)
        or set(predictions["horizon_months"]) != {1, 2, 3}
        or set(predictions["target_event"]) != set(TARGET_EVENTS)
        or set(predictions["model_id"]) != {"M0", "P1"}
    ):
        raise MatchedDegradationError("E6 prediction universe drifted")
    allowed_statuses = {
        "success",
        "input_ineligible",
        "target_unavailable",
        "model_unavailable",
        "numerical_failure",
        "infrastructure_failure",
    }
    if not predictions["terminal_status"].isin(allowed_statuses).all():
        raise MatchedDegradationError("E6 terminal status drifted")
    actual = pd.to_numeric(predictions["actual"], errors="coerce")
    score = pd.to_numeric(predictions["score"], errors="coerce")
    threshold = pd.to_numeric(predictions["threshold"], errors="coerce")
    success = predictions["terminal_status"].eq("success")
    if (
        not actual[success].isin([0, 1]).all()
        or not score[success].between(0.0, 1.0, inclusive="both").all()
        or not threshold[success].between(0.0, 1.0, inclusive="both").all()
    ):
        raise MatchedDegradationError("E6 successful prediction values drifted")
    unavailable = predictions["terminal_status"].eq("model_unavailable")
    if score[unavailable].notna().any() or threshold[unavailable].notna().any():
        raise MatchedDegradationError("E6 unavailable model fabricated a score or threshold")
    m0 = predictions["model_id"].eq("M0")
    p1 = predictions["model_id"].eq("P1")
    if (
        not predictions.loc[m0, "model_seed"].eq(1729).all()
        or not predictions.loc[p1, "model_seed"].eq(
            predictions.loc[p1, "degradation_seed"]
        ).all()
    ):
        raise MatchedDegradationError("E6 one-to-one model/degradation seed pairing drifted")
    for _, group in predictions.groupby(pair_identity, sort=True, dropna=False):
        if len(group) != 2 or set(group["model_id"]) != {"M0", "P1"}:
            raise MatchedDegradationError("E6 common M0/P1 row pair is incomplete")
        if group["actual"].nunique(dropna=False) != 1 or group["mask_sha256"].nunique() != 1:
            raise MatchedDegradationError("E6 paired target or common-mask binding drifted")
    base_identity = [
        "source_id",
        "site_id",
        "holdout_group_id",
        "common_origin_id",
        "horizon_months",
        "target_event",
    ]
    expected_scenario_seed = {(scenario, seed) for scenario in SCENARIOS for seed in SEEDS}
    for _, group in predictions.groupby(base_identity, sort=True, dropna=False):
        observed = set(zip(group["scenario_id"], group["degradation_seed"], strict=True))
        if observed != expected_scenario_seed or len(group) != 2 * len(expected_scenario_seed):
            raise MatchedDegradationError("E6 exact five-slot scenario coverage drifted")
        if group["actual"].nunique(dropna=False) != 1:
            raise MatchedDegradationError("E6 target changed across degradation slots")


def _paired_summary(metrics: pd.DataFrame) -> pd.DataFrame:
    index = ["scenario_id", "degradation_seed", "horizon_months", "target_event"]
    left = metrics[metrics["model_id"] == "M0"].set_index(index)
    right = metrics[metrics["model_id"] == "P1"].set_index(index)
    if not left.index.is_unique or not right.index.is_unique or not left.index.equals(right.index):
        raise MatchedDegradationError("E6 metric rows are not exactly paired")
    slot_rows: list[dict[str, Any]] = []
    for key in left.index:
        left_row, right_row = left.loc[key], right.loc[key]
        slot_rows.append({
            **dict(zip(index, cast(tuple[Any, Any, Any, Any], key), strict=True)),
            "delta_pr_auc_m0_minus_p1": float(left_row["pr_auc"] - right_row["pr_auc"]),
            "delta_brier_m0_minus_p1": float(left_row["brier"] - right_row["brier"]),
            "delta_recall_m0_minus_p1": float(left_row["recall"] - right_row["recall"]),
            "delta_f2_m0_minus_p1": float(left_row["f2"] - right_row["f2"]),
        })
    slots = pd.DataFrame(slot_rows)
    values = [column for column in slots if column.startswith("delta_")]
    return (
        slots.groupby(["scenario_id", "horizon_months", "target_event"], sort=True, as_index=False)
        .agg(slot_count=("degradation_seed", "nunique"), **{column: (column, "mean") for column in values})
    )


def _robustness_auc(metrics: pd.DataFrame) -> pd.DataFrame:
    families = {
        "mcar": (("control", 0.0), ("mcar_10", 0.10), ("mcar_25", 0.25), ("mcar_50", 0.50)),
        "block": (("control", 0.0), ("block_1m_10", 1.0), ("block_3m_10", 3.0), ("block_6m_25", 6.0)),
    }
    rows: list[dict[str, Any]] = []
    group_columns = ["model_id", "model_seed", "degradation_seed", "horizon_months", "target_event"]
    for raw_key, group in metrics.groupby(group_columns, sort=True):
        key = cast(tuple[Any, Any, Any, Any, Any], raw_key)
        model, model_seed, degradation_seed, horizon, endpoint = key
        by_scenario = group.set_index("scenario_id")
        for family, levels in families.items():
            if not all(scenario in by_scenario.index for scenario, _ in levels):
                continue
            control = by_scenario.loc["control"]
            for metric, orientation in (("pr_auc", "higher"), ("brier", "lower")):
                baseline = float(control[metric])
                x = np.asarray([level for _, level in levels], dtype="float64")
                retention: list[float] = []
                for scenario, _ in levels:
                    value = float(by_scenario.loc[scenario, metric])
                    denominator = baseline if orientation == "higher" else value
                    numerator = value if orientation == "higher" else baseline
                    ratio = (
                        numerator / denominator
                        if np.isfinite(numerator)
                        and np.isfinite(denominator)
                        and denominator != 0.0
                        else np.nan
                    )
                    retention.append(ratio if np.isfinite(ratio) else np.nan)
                y = np.asarray(retention, dtype="float64")
                aupd = (
                    float(np.trapezoid(y, x) / (x[-1] - x[0]))
                    if np.isfinite(y).all() and x[-1] > x[0]
                    else np.nan
                )
                rows.append({
                    "model_id": model,
                    "model_seed": int(model_seed),
                    "degradation_seed": int(degradation_seed),
                    "horizon_months": int(horizon),
                    "target_event": endpoint,
                    "degradation_family": family,
                    "metric": metric,
                    "retention_orientation": orientation,
                    "aupd": aupd,
                })
    return pd.DataFrame(rows)


def evaluate_matched_degradation(raw: pd.DataFrame, predictions: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if tuple(predictions.columns) != PREDICTION_COLUMNS:
        raise MatchedDegradationError("E6 prediction columns are not exact")
    _validate_prediction_universe(predictions)
    masks = build_common_degradation_masks(raw)
    digests = _mask_digests(masks)
    expected = predictions.apply(lambda row: digests.get((str(row["scenario_id"]), int(row["degradation_seed"]))), axis=1)
    if expected.isna().any() or not expected.eq(predictions["mask_sha256"]).all():
        raise MatchedDegradationError("E6 predictions are not bound to the common mask")
    metrics, failures = _metric_rows(predictions)
    pairwise = _paired_summary(metrics)
    if not pairwise["slot_count"].eq(len(SEEDS)).all() or len(pairwise) != len(SCENARIOS) * 3 * 2:
        raise MatchedDegradationError("E6 78-cell paired family-B summary drifted")
    return {"degradation_masks": masks, "matched_degradation_metrics": metrics, "matched_degradation_pairwise": pairwise, "failure_registry": failures, "robustness_auc": _robustness_auc(metrics)}


def _context(value: Mapping[str, Any]) -> tuple[Mapping[str, pd.DataFrame], Mapping[str, str]]:
    if set(value) != {"execution_id", "rng_seed", "tables", "stage_results", "model_availability", "software_evidence"} or type(value.get("execution_id")) is not str or not value["execution_id"] or type(value.get("rng_seed")) is not int or value["rng_seed"] != 1729 or not isinstance(value.get("tables"), Mapping) or not isinstance(value.get("stage_results"), Mapping) or not isinstance(value.get("model_availability"), Mapping) or not isinstance(value.get("software_evidence"), Mapping):
        raise MatchedDegradationError("E6 batch_context drifted")
    tables = cast(Mapping[str, Any], value["tables"])
    if any(type(table) is not pd.DataFrame for table in tables.values()):
        raise MatchedDegradationError("E6 tables are not DataFrames")
    availability = cast(Mapping[str, Any], value["model_availability"])
    if any(type(key) is not str or type(status) is not str for key, status in availability.items()):
        raise MatchedDegradationError("E6 model availability drifted")
    if set(cast(Mapping[str, Any], value["software_evidence"])) != {
        "public_tests_xml", "test_report", "openapi", "openapi_contract_report",
        "end_to_end_report", "environment",
    }:
        raise MatchedDegradationError("E6 software evidence keys drifted")
    return cast(Mapping[str, pd.DataFrame], tables), cast(Mapping[str, str], availability)


def _unavailable_result(reason: str) -> dict[str, Any]:
    empty = pd.DataFrame()
    tables = {"degradation_masks": empty.copy(), "matched_degradation_metrics": empty.copy(), "matched_degradation_pairwise": empty.copy(), "failure_registry": pd.DataFrame([{"reason": reason}]), "robustness_auc": empty.copy()}
    report = f"# Closure V1 E6 matched degradation\n\nStatus: unavailable\nReason: {reason}\n"
    artifacts = {OUTPUT_PATHS[0]: {"format": "parquet", "payload": tables["degradation_masks"], "manifest_last": False}, OUTPUT_PATHS[1]: {"format": "csv", "payload": tables["matched_degradation_metrics"], "manifest_last": False}, OUTPUT_PATHS[2]: {"format": "csv", "payload": tables["matched_degradation_pairwise"], "manifest_last": False}, OUTPUT_PATHS[3]: {"format": "csv", "payload": tables["failure_registry"], "manifest_last": False}, OUTPUT_PATHS[4]: {"format": "csv", "payload": tables["robustness_auc"], "manifest_last": False}, OUTPUT_PATHS[5]: {"format": "markdown", "payload": report, "manifest_last": True}}
    return {"component_id": COMPONENT_ID, "stage_id": STAGE_ID, "status": "completed_unavailable", "artifacts": artifacts, "tables": tables, "diagnostics": {"reason": reason, "refit_performed": False}, "outcome_paths_opened": True, "writes_performed": False}


def execute_closure_sealed_batch_component(authority: Mapping[str, Any], sealed_batch_contract: Mapping[str, Any], batch_context: Mapping[str, Any], repo_root: Path | None = None) -> dict[str, Any]:
    del repo_root
    _validate(authority, sealed_batch_contract)
    tables, availability = _context(batch_context)
    if dict(availability) != dict(
        cast(Mapping[str, Any], sealed_batch_contract.get("model_availability", {}))
    ):
        raise MatchedDegradationError("E6 model availability is not batch-bound")
    if availability.get("M0") != "available" or availability.get("P1") != "available":
        return _unavailable_result("M0_or_P1_model_unavailable_under_formal_lock")
    raw, predictions = tables.get(RAW_TABLE), tables.get(PREDICTION_TABLE)
    if type(raw) is not pd.DataFrame or type(predictions) is not pd.DataFrame:
        raise MatchedDegradationError("E6 required logical tables are absent")
    result = evaluate_matched_degradation(raw.copy(deep=True), predictions.copy(deep=True))
    report = "# Closure V1 E6 matched degradation\n\nCommon raw-cell masks were shared exactly by M0 and P1; no model was refit.\n"
    artifacts = {OUTPUT_PATHS[0]: {"format": "parquet", "payload": result["degradation_masks"], "manifest_last": False}, OUTPUT_PATHS[1]: {"format": "csv", "payload": result["matched_degradation_metrics"], "manifest_last": False}, OUTPUT_PATHS[2]: {"format": "csv", "payload": result["matched_degradation_pairwise"], "manifest_last": False}, OUTPUT_PATHS[3]: {"format": "csv", "payload": result["failure_registry"], "manifest_last": False}, OUTPUT_PATHS[4]: {"format": "csv", "payload": result["robustness_auc"], "manifest_last": False}, OUTPUT_PATHS[5]: {"format": "markdown", "payload": report, "manifest_last": True}}
    return {"component_id": COMPONENT_ID, "stage_id": STAGE_ID, "status": "completed", "artifacts": artifacts, "tables": result, "diagnostics": {"scenario_count": len(SCENARIOS), "ordered_seed_slot_count": len(SEEDS), "common_mask_required": True, "refit_performed": False}, "outcome_paths_opened": True, "writes_performed": False}


__all__ = ["MatchedDegradationError", "component_contract", "component_contract_sha256", "build_common_degradation_masks", "evaluate_matched_degradation", "preflight_closure_sealed_batch_component", "execute_closure_sealed_batch_component"]
