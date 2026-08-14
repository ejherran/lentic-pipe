#!/usr/bin/env python
"""Pure deterministic E4 ordinal trophic-state evaluation component."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, cast

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix, f1_score, recall_score


COMPONENT_ID = "E4_trophic_evaluation"
STAGE_ID = "E4"
PREDICTION_TABLE = "trophic_predictions"
REFERENCE_TABLE = "trophic_reference_targets"
NLA_TABLE = "nla_trophic_semantic"
CLASS_ORDER = ("oligotrophic", "mesotrophic", "eutrophic", "hypereutrophic")
REGISTERED_SEEDS = (1729, 20260612, 20260613, 20260614, 314159)
OUTPUT_PATHS = (
    "reports/closure_v1/04_trophic/trophic_proxy_metrics.csv",
    "reports/closure_v1/04_trophic/carlson_reference_metrics.csv",
    "reports/closure_v1/04_trophic/trophic_confusion_matrices.csv",
    "reports/closure_v1/04_trophic/nla_semantic_metrics.csv",
    "reports/closure_v1/04_trophic/trophic_validation_report.md",
)
PREDICTION_COLUMNS = (
    "source_id",
    "site_id",
    "holdout_group_id",
    "common_origin_id",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
    "model_id",
    "model_seed",
    "seed_slot",
    "terminal_status",
    "ordinal_score",
    "cutpoint_1",
    "cutpoint_2",
    "cutpoint_3",
)
JOIN_COLUMNS = (
    "source_id",
    "site_id",
    "holdout_group_id",
    "common_origin_id",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
)
REFERENCE_COLUMNS = (
    *JOIN_COLUMNS,
    "future_chlorophyll_a_ugL",
    "operational_trophic_state",
    "tsi_tp_h",
    "tsi_sd_h",
    "tsi_chla_h",
    "tsi_non_chla_h",
    "tsi_all_h",
    "tsi_tp_h_class",
    "tsi_sd_h_class",
    "tsi_chla_h_class",
    "tsi_non_chla_h_class",
    "tsi_all_h_class",
    "non_chla_reference_available",
    "all_reference_indicator_count",
)
COMPONENT_CONTRACT = {
    "schema_version": "closure_e4_trophic_evaluation_v1",
    "component_id": COMPONENT_ID,
    "stage_id": STAGE_ID,
    "input_tables": [PREDICTION_TABLE, REFERENCE_TABLE],
    "optional_input_tables": [NLA_TABLE],
    "classes_in_order": list(CLASS_ORDER),
    "metrics": ["macro_f1", "quadratic_weighted_kappa", "ordinal_mae", "severe_error_rate", "recall_by_class"],
    "carlson_references": ["tsi_tp_h", "tsi_sd_h", "tsi_non_chla_h", "tsi_all_h"],
    "nla_role": "cross_sectional_semantic_only_not_temporal_validation",
    "output_paths": list(OUTPUT_PATHS),
    "filesystem_writes": "forbidden",
}


class TrophicStateEvaluationError(RuntimeError):
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
        raise TrophicStateEvaluationError("E4 E0-U authority drifted")
    if contract.get("schema_version") != "closure_sealed_evaluation_batch_v1" or contract.get("experiment_id") != "closure_v1" or contract.get("execution_gate") != "E0-U" or contract.get("evaluation_refit") != "forbidden" or contract.get("failed_model_replacement") != "forbidden" or contract.get("silent_row_deletion") != "forbidden" or contract.get("one_batch_only") is not True or authority.get("sealed_batch_command") != contract.get("sealed_command"):
        raise TrophicStateEvaluationError("E4 sealed batch contract drifted")
    expected = {"component_id": COMPONENT_ID, "stage_id": STAGE_ID, "module_name": "src.experiments.evaluate_trophic_state", "source_path": "src/experiments/evaluate_trophic_state.py", "preflight_api": "preflight_closure_sealed_batch_component", "execute_api": "execute_closure_sealed_batch_component"}
    if not isinstance(contract.get("components"), list) or cast(list[Any], contract["components"]).count(expected) != 1:
        raise TrophicStateEvaluationError("E4 component registration drifted")
    return _digest(contract)


def preflight_closure_sealed_batch_component(authority: Mapping[str, Any], sealed_batch_contract: Mapping[str, Any], repo_root: Path | None = None) -> dict[str, Any]:
    del repo_root
    return {"component_id": COMPONENT_ID, "stage_id": STAGE_ID, "status": "ready", "contract_sha256": _validate(authority, sealed_batch_contract), "outcome_paths_opened": False, "writes_performed": False}


def _context(value: Mapping[str, Any]) -> tuple[Mapping[str, pd.DataFrame], Mapping[str, str]]:
    if set(value) != {"execution_id", "rng_seed", "tables", "stage_results", "model_availability", "software_evidence"} or type(value.get("execution_id")) is not str or not value["execution_id"] or value.get("rng_seed") != 1729 or type(value.get("rng_seed")) is not int or not isinstance(value.get("tables"), Mapping) or not isinstance(value.get("stage_results"), Mapping) or not isinstance(value.get("model_availability"), Mapping) or not isinstance(value.get("software_evidence"), Mapping):
        raise TrophicStateEvaluationError("E4 batch_context drifted")
    tables = cast(Mapping[str, Any], value["tables"])
    if any(type(table) is not pd.DataFrame for table in tables.values()):
        raise TrophicStateEvaluationError("E4 tables are not DataFrames")
    availability = cast(Mapping[str, Any], value["model_availability"])
    if any(type(k) is not str or type(v) is not str for k, v in availability.items()):
        raise TrophicStateEvaluationError("E4 model availability drifted")
    if set(cast(Mapping[str, Any], value["software_evidence"])) != {
        "public_tests_xml", "test_report", "openapi", "openapi_contract_report",
        "end_to_end_report", "environment",
    }:
        raise TrophicStateEvaluationError("E4 software evidence keys drifted")
    return cast(Mapping[str, pd.DataFrame], tables), cast(Mapping[str, str], availability)


def _ordinal_metrics(actual: pd.Series, predicted: pd.Series) -> dict[str, Any]:
    valid = actual.isin(CLASS_ORDER) & predicted.isin(CLASS_ORDER)
    a = actual[valid].astype(str)
    p = predicted[valid].astype(str)
    if a.empty:
        return {"rows": 0, "macro_f1": np.nan, "quadratic_weighted_kappa": np.nan, "ordinal_mae": np.nan, "severe_error_rate": np.nan, **{f"recall_{label}": np.nan for label in CLASS_ORDER}}
    ranks = {label: index for index, label in enumerate(CLASS_ORDER)}
    ar = a.map(ranks).to_numpy(dtype="int64")
    pr = p.map(ranks).to_numpy(dtype="int64")
    recalls = recall_score(a, p, labels=list(CLASS_ORDER), average=None, zero_division=0)
    kappa = (
        float(cohen_kappa_score(ar, pr, weights="quadratic"))
        if np.unique(np.concatenate((ar, pr))).size > 1
        else np.nan
    )
    return {
        "rows": len(a),
        "macro_f1": float(f1_score(a, p, labels=list(CLASS_ORDER), average="macro", zero_division=0)),
        "quadratic_weighted_kappa": kappa,
        "ordinal_mae": float(np.mean(np.abs(ar - pr))),
        "severe_error_rate": float(np.mean(np.abs(ar - pr) >= 2)),
        **{f"recall_{label}": float(value) for label, value in zip(CLASS_ORDER, recalls, strict=True)},
    }


def _group_metrics(frame: pd.DataFrame, actual_column: str, reference: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    matrices: list[dict[str, Any]] = []
    keys = ["model_id", "model_seed", "seed_slot", "horizon_months"]
    for raw_group_key, group in frame.groupby(keys, sort=True, dropna=False):
        group_key = cast(tuple[Any, Any, Any, Any], raw_group_key)
        model_id, model_seed, seed_slot, horizon = group_key
        metrics = _ordinal_metrics(group[actual_column], group["predicted_trophic_state"])
        valid = group[actual_column].isin(CLASS_ORDER) & group["predicted_trophic_state"].isin(CLASS_ORDER)
        rows.append({"reference": reference, "model_id": model_id, "model_seed": model_seed, "seed_slot": int(seed_slot), "horizon_months": int(horizon), "site_count": int(group.loc[valid, ["source_id", "site_id"]].drop_duplicates().shape[0]), **metrics})
        matrix = (
            confusion_matrix(
                group.loc[valid, actual_column],
                group.loc[valid, "predicted_trophic_state"],
                labels=list(CLASS_ORDER),
            )
            if valid.any()
            else np.zeros((len(CLASS_ORDER), len(CLASS_ORDER)), dtype="int64")
        )
        for ai, actual in enumerate(CLASS_ORDER):
            for pi, predicted in enumerate(CLASS_ORDER):
                matrices.append({"reference": reference, "model_id": model_id, "model_seed": model_seed, "seed_slot": int(seed_slot), "horizon_months": int(horizon), "actual_class": actual, "predicted_class": predicted, "rows": int(matrix[ai, pi])})
    return pd.DataFrame(rows), pd.DataFrame(matrices)


def evaluate_trophic_state(predictions: pd.DataFrame, references: pd.DataFrame, nla: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    if tuple(predictions.columns) != PREDICTION_COLUMNS:
        raise TrophicStateEvaluationError("E4 prediction columns are not exact")
    if predictions.duplicated([*JOIN_COLUMNS, "model_id", "model_seed", "seed_slot"]).any():
        raise TrophicStateEvaluationError("E4 prediction keys are not unique")
    if (
        predictions.empty
        or not predictions["horizon_months"].isin([1, 2, 3]).all()
        or not predictions["seed_slot"].isin(REGISTERED_SEEDS).all()
        or predictions[list(JOIN_COLUMNS) + ["model_id", "model_seed", "seed_slot", "terminal_status"]].isna().any().any()
    ):
        raise TrophicStateEvaluationError("E4 prediction identity drifted")
    terminal_statuses = {
        "success", "input_ineligible", "target_unavailable", "model_unavailable",
        "numerical_failure", "infrastructure_failure",
    }
    if not predictions["terminal_status"].isin(terminal_statuses).all():
        raise TrophicStateEvaluationError("E4 terminal status drifted")
    if tuple(references.columns) != REFERENCE_COLUMNS:
        raise TrophicStateEvaluationError("E4 reference columns are not exact")
    if references.duplicated(list(JOIN_COLUMNS)).any():
        raise TrophicStateEvaluationError("E4 reference keys are not unique")
    prediction_keys = predictions.loc[:, list(JOIN_COLUMNS)].drop_duplicates()
    reference_keys = references.loc[:, list(JOIN_COLUMNS)]
    key_check = prediction_keys.merge(
        reference_keys,
        on=list(JOIN_COLUMNS),
        how="outer",
        indicator=True,
        validate="one_to_one",
    )
    if len(key_check) != len(reference_keys) or not key_check["_merge"].eq("both").all():
        raise TrophicStateEvaluationError(
            "E4 prediction/reference locked test keysets are not identical"
        )
    cutpoints = predictions[["cutpoint_1", "cutpoint_2", "cutpoint_3"]].apply(
        pd.to_numeric, errors="coerce"
    )
    score = pd.to_numeric(predictions["ordinal_score"], errors="coerce")
    success = predictions["terminal_status"].eq("success")
    if (
        cutpoints.loc[success].isna().any().any()
        or not (
            cutpoints.loc[success, "cutpoint_1"]
            < cutpoints.loc[success, "cutpoint_2"]
        ).all()
        or not (
            cutpoints.loc[success, "cutpoint_2"]
            < cutpoints.loc[success, "cutpoint_3"]
        ).all()
    ):
        raise TrophicStateEvaluationError("E4 locked ordinal cutpoints drifted")
    if score[success].isna().any() or not score[success].between(0.0, 1.0).all():
        raise TrophicStateEvaluationError("E4 successful ordinal score is not finite")
    unavailable = predictions["terminal_status"].eq("model_unavailable")
    if score[unavailable].notna().any():
        raise TrophicStateEvaluationError("E4 unavailable model fabricated an ordinal score")
    for _, group in predictions.loc[success].groupby(
        ["model_id", "model_seed", "horizon_months"], sort=True
    ):
        if any(group[column].nunique(dropna=False) != 1 for column in cutpoints):
            raise TrophicStateEvaluationError("E4 ordinal cutpoints changed after locking")
    decoded = np.full(len(predictions), None, dtype=object)
    decoded[success & (score < cutpoints["cutpoint_1"])] = CLASS_ORDER[0]
    decoded[success & (score >= cutpoints["cutpoint_1"]) & (score < cutpoints["cutpoint_2"])] = CLASS_ORDER[1]
    decoded[success & (score >= cutpoints["cutpoint_2"]) & (score < cutpoints["cutpoint_3"])] = CLASS_ORDER[2]
    decoded[success & (score >= cutpoints["cutpoint_3"])] = CLASS_ORDER[3]
    prediction_work = predictions.copy(deep=True)
    prediction_work["predicted_trophic_state"] = pd.Categorical(
        decoded, categories=CLASS_ORDER, ordered=True
    )
    merged = prediction_work.merge(
        references,
        on=list(JOIN_COLUMNS),
        how="left",
        validate="many_to_one",
        indicator=True,
    )
    if not merged["_merge"].eq("both").all():
        raise TrophicStateEvaluationError("E4 prediction/reference cohort is not exact")
    merged = merged.drop(columns="_merge")
    proxy, proxy_matrix = _group_metrics(merged, "operational_trophic_state", "future_chla_operational_proxy")
    carlson_parts: list[pd.DataFrame] = []
    matrices = [proxy_matrix]
    for column in ("tsi_tp_h_class", "tsi_sd_h_class", "tsi_non_chla_h_class", "tsi_all_h_class"):
        metric, matrix = _group_metrics(merged, column, column.removesuffix("_class"))
        carlson_parts.append(metric)
        matrices.append(matrix)
    carlson = pd.concat(carlson_parts, ignore_index=True) if carlson_parts else pd.DataFrame()
    nla_metrics = pd.DataFrame()
    if nla is not None:
        expected_nla = (
            "source_id", "site_id", "model_id", "model_seed", "seed_slot",
            "actual_trophic_state", "predicted_trophic_state",
        )
        if tuple(nla.columns) != expected_nla:
            raise TrophicStateEvaluationError("E4 NLA semantic columns are not exact")
        nla_work = nla.assign(horizon_months=0)
        nla_metrics, nla_matrix = _group_metrics(nla_work, "actual_trophic_state", "nla_cross_sectional_semantic")
        matrices.append(nla_matrix)
    return {"trophic_proxy_metrics": proxy, "carlson_reference_metrics": carlson, "trophic_confusion_matrices": pd.concat(matrices, ignore_index=True), "nla_semantic_metrics": nla_metrics}


def _report(tables: Mapping[str, pd.DataFrame], unavailable: list[str]) -> str:
    return "\n".join(["# Closure V1 E4 trophic validation", "", f"Operational rows: {len(tables['trophic_proxy_metrics'])}", f"Carlson rows: {len(tables['carlson_reference_metrics'])}", f"Unavailable models retained: {','.join(unavailable) if unavailable else 'none'}", "", "Carlson non-Chl-a targets were never imputed; NLA is semantic and cross-sectional only.", ""])


def execute_closure_sealed_batch_component(authority: Mapping[str, Any], sealed_batch_contract: Mapping[str, Any], batch_context: Mapping[str, Any], repo_root: Path | None = None) -> dict[str, Any]:
    del repo_root
    _validate(authority, sealed_batch_contract)
    tables, availability = _context(batch_context)
    if dict(availability) != dict(
        cast(Mapping[str, Any], sealed_batch_contract.get("model_availability", {}))
    ):
        raise TrophicStateEvaluationError("E4 model availability is not batch-bound")
    predictions = tables.get(PREDICTION_TABLE)
    references = tables.get(REFERENCE_TABLE)
    if type(predictions) is not pd.DataFrame or type(references) is not pd.DataFrame:
        raise TrophicStateEvaluationError("E4 required logical tables are absent")
    unavailable = sorted(model for model, status in availability.items() if status != "available")
    nla_source = tables.get(NLA_TABLE)
    nla = nla_source.copy(deep=True) if isinstance(nla_source, pd.DataFrame) else None
    evaluated = evaluate_trophic_state(
        predictions.copy(deep=True), references.copy(deep=True), nla
    )
    report = _report(evaluated, unavailable)
    artifacts: dict[str, dict[str, Any]] = {
        OUTPUT_PATHS[0]: {"format": "csv", "payload": evaluated["trophic_proxy_metrics"], "manifest_last": False},
        OUTPUT_PATHS[1]: {"format": "csv", "payload": evaluated["carlson_reference_metrics"], "manifest_last": False},
        OUTPUT_PATHS[2]: {"format": "csv", "payload": evaluated["trophic_confusion_matrices"], "manifest_last": False},
        OUTPUT_PATHS[3]: {"format": "csv", "payload": evaluated["nla_semantic_metrics"], "manifest_last": False},
        OUTPUT_PATHS[4]: {"format": "markdown", "payload": report, "manifest_last": True},
    }
    return {"component_id": COMPONENT_ID, "stage_id": STAGE_ID, "status": "completed", "artifacts": artifacts, "tables": evaluated, "diagnostics": {"unavailable_model_ids": unavailable, "nla_temporal_validation_claimed": False, "future_indicator_imputation_performed": False}, "outcome_paths_opened": True, "writes_performed": False}


__all__ = ["TrophicStateEvaluationError", "component_contract", "component_contract_sha256", "evaluate_trophic_state", "preflight_closure_sealed_batch_component", "execute_closure_sealed_batch_component"]
