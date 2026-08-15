#!/usr/bin/env python
"""Build outcome-time trophic references for the sealed Closure V1 E4 batch.

This module is deliberately pure: the runner supplies already-authorized outcome
rows in ``batch_context`` and receives DataFrames back.  No path is resolved and
no file is read or written here.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, cast

import numpy as np
import pandas as pd


COMPONENT_ID = "E4_reference_targets"
STAGE_ID = "E4"
INPUT_TABLE = "future_trophic_indicators"
OUTPUT_TABLE = "trophic_reference_targets"
CLASS_ORDER = ("oligotrophic", "mesotrophic", "eutrophic", "hypereutrophic")
INPUT_COLUMNS = (
    "source_id",
    "site_id",
    "holdout_group_id",
    "common_origin_id",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
    "evaluation_cohort",
    "evaluation_role",
    "future_TP_ugL",
    "future_secchi_depth_m",
    "future_chlorophyll_a_ugL",
)
KEY_COLUMNS = (
    "source_id",
    "site_id",
    "holdout_group_id",
    "common_origin_id",
    "origin_year_month",
    "target_year_month",
    "horizon_months",
    "evaluation_cohort",
    "evaluation_role",
)
COMPONENT_CONTRACT = {
    "schema_version": "closure_e4_trophic_reference_targets_v1",
    "component_id": COMPONENT_ID,
    "stage_id": STAGE_ID,
    "input_table": INPUT_TABLE,
    "input_columns": list(INPUT_COLUMNS),
    "output_table": OUTPUT_TABLE,
    "carlson_equations": {
        "tsi_tp": "14.42*ln(future_TP_ugL)+4.15",
        "tsi_sd": "60-14.41*ln(future_secchi_depth_m)",
        "tsi_chla": "9.81*ln(future_chlorophyll_a_ugL)+30.6",
    },
    "class_cutpoints": [40.0, 50.0, 70.0],
    "operational_chla_cutpoints_ugL": [2.6, 7.3, 56.0],
    "tsi_non_chla_rule": "median_tp_sd_only_when_both_observed",
    "tsi_all_rule": "median_of_observed_tp_sd_chla",
    "future_indicator_imputation": "forbidden",
    "source_id": "wqp",
    "evaluation_cohort": "location_holdout",
    "evaluation_role": "test",
    "outcome_boundary": "target_year_month_after_2021_12",
    "same_target_month_required": True,
    "filesystem_writes": "forbidden",
}


class TrophicReferenceTargetsError(RuntimeError):
    """Raised when the closed E4 reference contract is violated."""


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    payload = (
        json.dumps(
            dict(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def component_contract() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(json.dumps(COMPONENT_CONTRACT)))


def component_contract_sha256() -> str:
    return _canonical_sha256(COMPONENT_CONTRACT)


def _validate_authority_and_batch(
    authority: Mapping[str, Any], sealed_batch_contract: Mapping[str, Any]
) -> str:
    required = {
        "gate": "E0-U",
        "effective_authority": True,
        "sealed_batch_execution_authorized": True,
        "e0_m_authorized": True,
        "e0_u_authorized": True,
        "evaluation_authorized": True,
        "outcome_access_authorized": True,
        "writes_performed": False,
    }
    if any(type(authority.get(k)) is not type(v) or authority.get(k) != v for k, v in required.items()):
        raise TrophicReferenceTargetsError("E4 effective E0-U authority drifted")
    if (
        sealed_batch_contract.get("schema_version")
        != "closure_sealed_evaluation_batch_v1"
        or sealed_batch_contract.get("experiment_id") != "closure_v1"
        or sealed_batch_contract.get("execution_gate") != "E0-U"
        or sealed_batch_contract.get("evaluation_refit") != "forbidden"
        or sealed_batch_contract.get("failed_model_replacement") != "forbidden"
        or sealed_batch_contract.get("silent_row_deletion") != "forbidden"
        or sealed_batch_contract.get("one_batch_only") is not True
        or authority.get("sealed_batch_command")
        != sealed_batch_contract.get("sealed_command")
    ):
        raise TrophicReferenceTargetsError("E4 sealed batch contract drifted")
    components = sealed_batch_contract.get("components")
    expected = {
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "module_name": "src.experiments.build_trophic_reference_targets",
        "source_path": "src/experiments/build_trophic_reference_targets.py",
        "preflight_api": "preflight_closure_sealed_batch_component",
        "execute_api": "execute_closure_sealed_batch_component",
    }
    if not isinstance(components, list) or components.count(expected) != 1:
        raise TrophicReferenceTargetsError("E4 component registration drifted")
    return _canonical_sha256(sealed_batch_contract)


def preflight_closure_sealed_batch_component(
    authority: Mapping[str, Any],
    sealed_batch_contract: Mapping[str, Any],
    repo_root: Path | None = None,
) -> dict[str, Any]:
    del repo_root
    digest = _validate_authority_and_batch(authority, sealed_batch_contract)
    return {
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "status": "ready",
        "contract_sha256": digest,
        "outcome_paths_opened": False,
        "writes_performed": False,
    }


def _validate_context(batch_context: Mapping[str, Any]) -> Mapping[str, pd.DataFrame]:
    if set(batch_context) != {
        "execution_id", "rng_seed", "tables", "stage_results", "model_availability",
        "software_evidence",
    }:
        raise TrophicReferenceTargetsError("E4 batch_context keys drifted")
    if (
        type(batch_context.get("execution_id")) is not str
        or not batch_context["execution_id"]
        or type(batch_context.get("rng_seed")) is not int
        or batch_context["rng_seed"] != 1729
        or not isinstance(batch_context.get("tables"), Mapping)
        or not isinstance(batch_context.get("stage_results"), Mapping)
        or not isinstance(batch_context.get("model_availability"), Mapping)
        or not isinstance(batch_context.get("software_evidence"), Mapping)
    ):
        raise TrophicReferenceTargetsError("E4 batch_context value drifted")
    tables = cast(Mapping[str, Any], batch_context["tables"])
    if any(type(value) is not pd.DataFrame for value in tables.values()):
        raise TrophicReferenceTargetsError("E4 batch_context tables must be DataFrames")
    availability = cast(Mapping[str, Any], batch_context["model_availability"])
    if any(type(key) is not str or type(status) is not str for key, status in availability.items()):
        raise TrophicReferenceTargetsError("E4 model availability drifted")
    if cast(Mapping[str, Any], batch_context["software_evidence"]):
        raise TrophicReferenceTargetsError("E4 received unrelated software evidence")
    return cast(Mapping[str, pd.DataFrame], tables)


def _optional_nonnegative_numeric(frame: pd.DataFrame, column: str) -> np.ndarray:
    source = frame[column]
    numeric = pd.to_numeric(source, errors="coerce")
    invalid = source.notna() & (~numeric.map(np.isfinite) | numeric.lt(0.0))
    if invalid.any():
        raise TrophicReferenceTargetsError(f"E4 future indicator is invalid: {column}")
    return numeric.to_numpy(dtype="float64")


def _tsi_class(values: np.ndarray) -> pd.Categorical:
    labels = np.full(values.shape, None, dtype=object)
    valid = np.isfinite(values)
    labels[valid & (values < 40.0)] = CLASS_ORDER[0]
    labels[valid & (values >= 40.0) & (values < 50.0)] = CLASS_ORDER[1]
    labels[valid & (values >= 50.0) & (values < 70.0)] = CLASS_ORDER[2]
    labels[valid & (values >= 70.0)] = CLASS_ORDER[3]
    return pd.Categorical(labels, categories=CLASS_ORDER, ordered=True)


def _operational_chla_class(values: np.ndarray) -> pd.Categorical:
    labels = np.full(values.shape, None, dtype=object)
    valid = np.isfinite(values)
    labels[valid & (values < 2.6)] = CLASS_ORDER[0]
    labels[valid & (values >= 2.6) & (values < 7.3)] = CLASS_ORDER[1]
    labels[valid & (values >= 7.3) & (values < 56.0)] = CLASS_ORDER[2]
    labels[valid & (values >= 56.0)] = CLASS_ORDER[3]
    return pd.Categorical(labels, categories=CLASS_ORDER, ordered=True)


def build_trophic_reference_targets(frame: pd.DataFrame) -> pd.DataFrame:
    """Compute Carlson references without imputing absent future indicators."""
    if tuple(frame.columns) != INPUT_COLUMNS:
        raise TrophicReferenceTargetsError("E4 future indicator columns are not exact")
    if frame.empty:
        raise TrophicReferenceTargetsError("E4 future indicator table is empty")
    if frame[list(KEY_COLUMNS)].isna().any().any():
        raise TrophicReferenceTargetsError("E4 reference identity contains nulls")
    for column in (
        "source_id",
        "site_id",
        "holdout_group_id",
        "common_origin_id",
        "origin_year_month",
        "target_year_month",
        "evaluation_cohort",
        "evaluation_role",
    ):
        if frame[column].astype(str).str.len().eq(0).any():
            raise TrophicReferenceTargetsError(f"E4 reference identity drifted: {column}")
    if frame.duplicated(list(KEY_COLUMNS)).any():
        raise TrophicReferenceTargetsError("E4 future indicator keys are not unique")
    if not frame["common_origin_id"].astype(str).str.fullmatch(r"[0-9a-f]{64}").all():
        raise TrophicReferenceTargetsError("E4 common-origin identity is not canonical")
    if (
        not frame["source_id"].eq("wqp").all()
        or not frame["evaluation_cohort"].eq("location_holdout").all()
        or not frame["evaluation_role"].eq("test").all()
    ):
        raise TrophicReferenceTargetsError(
            "E4 references are not restricted to locked location holdout test rows"
        )
    horizons = pd.to_numeric(frame["horizon_months"], errors="coerce")
    if horizons.isna().any() or not horizons.isin([1, 2, 3]).all():
        raise TrophicReferenceTargetsError("E4 horizons are not exact 1/2/3")
    try:
        origins = pd.PeriodIndex(frame["origin_year_month"].astype(str), freq="M")
        targets = pd.PeriodIndex(frame["target_year_month"].astype(str), freq="M")
    except (TypeError, ValueError) as exc:
        raise TrophicReferenceTargetsError("E4 month identity is invalid") from exc
    expected_targets = pd.PeriodIndex(
        [origin + int(horizon) for origin, horizon in zip(origins, horizons, strict=True)],
        freq="M",
    )
    if not targets.equals(expected_targets):
        raise TrophicReferenceTargetsError("E4 reference is not from the prediction target month")
    if not (targets > pd.Period("2021-12", freq="M")).all():
        raise TrophicReferenceTargetsError("E4 reference is outside the sealed post-2021 outcome boundary")
    tp = _optional_nonnegative_numeric(frame, "future_TP_ugL")
    sd = _optional_nonnegative_numeric(frame, "future_secchi_depth_m")
    chla = _optional_nonnegative_numeric(frame, "future_chlorophyll_a_ugL")
    tsi_tp = 14.42 * np.log(np.where(tp > 0.0, tp, np.nan)) + 4.15
    tsi_sd = 60.0 - 14.41 * np.log(np.where(sd > 0.0, sd, np.nan))
    tsi_chla = 9.81 * np.log(np.where(chla > 0.0, chla, np.nan)) + 30.6
    non_chla = np.where(np.isfinite(tsi_tp) & np.isfinite(tsi_sd), (tsi_tp + tsi_sd) / 2.0, np.nan)
    stacked = np.column_stack((tsi_tp, tsi_sd, tsi_chla))
    counts = np.isfinite(stacked).sum(axis=1)
    all_tsi = np.full(len(frame), np.nan, dtype="float64")
    for indicator_count in (1, 2, 3):
        selected = counts == indicator_count
        if selected.any():
            all_tsi[selected] = np.nanmedian(stacked[selected], axis=1)
    output = frame.loc[:, list(KEY_COLUMNS)].copy()
    output["future_chlorophyll_a_ugL"] = chla
    output["operational_trophic_state"] = _operational_chla_class(chla)
    output["tsi_tp_h"] = tsi_tp
    output["tsi_sd_h"] = tsi_sd
    output["tsi_chla_h"] = tsi_chla
    output["tsi_non_chla_h"] = non_chla
    output["tsi_all_h"] = all_tsi
    for name in ("tsi_tp_h", "tsi_sd_h", "tsi_chla_h", "tsi_non_chla_h", "tsi_all_h"):
        output[f"{name}_class"] = _tsi_class(output[name].to_numpy(dtype="float64"))
    output["non_chla_reference_available"] = np.isfinite(non_chla)
    output["all_reference_indicator_count"] = counts.astype("int8")
    return output.sort_values(list(KEY_COLUMNS), kind="mergesort").reset_index(drop=True)


def execute_closure_sealed_batch_component(
    authority: Mapping[str, Any],
    sealed_batch_contract: Mapping[str, Any],
    batch_context: Mapping[str, Any],
    repo_root: Path | None = None,
) -> dict[str, Any]:
    del repo_root
    _validate_authority_and_batch(authority, sealed_batch_contract)
    tables = _validate_context(batch_context)
    if dict(cast(Mapping[str, Any], batch_context["model_availability"])) != dict(
        cast(Mapping[str, Any], sealed_batch_contract.get("model_availability", {}))
    ):
        raise TrophicReferenceTargetsError("E4 model availability is not batch-bound")
    frame = tables.get(INPUT_TABLE)
    if type(frame) is not pd.DataFrame:
        raise TrophicReferenceTargetsError(f"E4 input table is absent: {INPUT_TABLE}")
    result = build_trophic_reference_targets(frame.copy(deep=True))
    return {
        "component_id": COMPONENT_ID,
        "stage_id": STAGE_ID,
        "status": "completed",
        "artifacts": {},
        "tables": {OUTPUT_TABLE: result},
        "diagnostics": {
            "row_count": len(result),
            "site_count": int(result[["source_id", "site_id"]].drop_duplicates().shape[0]),
            "non_chla_reference_row_count": int(result["non_chla_reference_available"].sum()),
            "future_indicator_imputation_performed": False,
        },
        "outcome_paths_opened": True,
        "writes_performed": False,
    }


__all__ = [
    "TrophicReferenceTargetsError", "component_contract", "component_contract_sha256",
    "build_trophic_reference_targets", "preflight_closure_sealed_batch_component",
    "execute_closure_sealed_batch_component",
]
